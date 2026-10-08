import numpy as np

from scenario import (
    AWD_THRESHOLD_CM,
    FILL_LEVEL_CM,
    MAX_DRY_DAYS_POORLY_DRAINED,
    NO_DRYING_STAGES,
    crop_coefficient,
    level_to_storage,
    step_level,
)

BASELINE_TRIGGER_CM = -5.0

AGENT_SY = 0.25
AGENT_PRIOR_LOSS_MM = 4.0
SENSOR_PHOTO_CONFLICT_CM = 5.0
SENSOR_MODEL_CONFLICT_CM = 6.0
PHOTO_MODEL_CONFLICT_CM = 8.0
AGREE_CM = 3.0
CONFIRM_PHOTO_CM = 4.0
STALE_DAYS = 2
MISSING_LOG_DAYS = 3
REPAIR_DELAY_DAYS = 3
AWD_MARGIN_CM = 2.0
WET_MARGIN_CM = 0.5
FORECAST_DAYS = 2
LOSS_GAIN = 0.05
SENSOR_RANGE_MIN_CM = -29.5
BLEND = 0.7


class PolicyBase:
    name = "base"

    def reset(self, sc):
        self.sc = sc
        self.remeasure_requests = set()
        self.escalated = set()
        self.sensor_repair_day = {}
        self.actions = []
        self.detections = []
        self.evidence = {}

    def act(self, pid, day, action, note=""):
        self.actions.append({"pid": pid, "day": day, "action": action, "note": note})

    def confirm(self, day, irrigated, irrigation_mm):
        pass


class BaselinePolicy(PolicyBase):
    name = "baseline"

    def reset(self, sc):
        super().reset(sc)
        self.last_report = {}

    def step(self, day, obs):
        for pid, o in obs.items():
            value = o["photo"] if o["photo"] is not None else o["sensor"]
            if value is not None:
                self.last_report[pid] = value
                self.evidence[(pid, day)] = value
        orders = {}
        for c, runs in self.sc.actual_runs.items():
            if day not in runs:
                continue
            queue = []
            for p in self.sc.plots:
                if p.cluster != c or p.slot != runs[day] or not p.active(day):
                    continue
                st = p.stage(day)
                last = self.last_report.get(p.pid)
                if st in NO_DRYING_STAGES or (st == "awd" and (last is None or last <= BASELINE_TRIGGER_CM)):
                    queue.append(p.pid)
                    self.act(p.pid, day, "irrigate")
            for p in self.sc.plots:
                spare = len(queue) < self.sc.pump_capacity
                if spare and p.cluster == c and p.pid not in queue and p.active(day) and p.stage(day) in NO_DRYING_STAGES:
                    queue.append(p.pid)
                    self.act(p.pid, day, "irrigate")
            orders[c] = queue
        return orders


class AgentPolicy(PolicyBase):
    name = "agent"

    def reset(self, sc):
        super().reset(sc)
        self.est = {}
        self.loss = {p.pid: AGENT_PRIOR_LOSS_MM for p in sc.plots}
        self.last_trusted = {p.pid: p.sowing_day for p in sc.plots}
        self.sensor_history = {p.pid: [] for p in sc.plots}
        self.expected_delta = {p.pid: [] for p in sc.plots}
        self.flagged = {}
        self.pending = {}
        self.last_covered = {p.pid: p.sowing_day - 1 for p in sc.plots}
        self.dry_streak = {p.pid: 0 for p in sc.plots}
        self.known_cancelled = set()

    def known_runs(self, c, day):
        runs = dict(self.sc.planned_runs[c])
        for ch in self.sc.schedule_changes:
            if ch["cluster"] != c:
                continue
            if ch["announced_day"] is not None and ch["announced_day"] <= day:
                runs[ch["new_day"]] = runs.pop(ch["day"])
            if (c, ch["day"]) in self.known_cancelled:
                runs.pop(ch["day"], None)
        return runs

    def forecast_rain(self, plot, day, origin):
        if day - origin >= FORECAST_DAYS:
            return 0.0
        return self.sc.rain[plot.site][day] * self.sc.forecast_factor[plot.cluster, day]

    def propagate(self, plot, h, day, rain):
        flux = rain - crop_coefficient(plot.k(day)) * self.sc.et0[plot.site][day] - self.loss[plot.pid]
        return step_level(h, flux, AGENT_SY)

    def flag_sensor(self, plot, day, reason):
        self.flagged[plot.pid] = day
        self.sensor_repair_day[plot.pid] = day + REPAIR_DELAY_DAYS
        self.detections.append({"fault": "a_sensor", "pid": plot.pid, "cluster": plot.cluster, "day": day, "ref_day": day, "note": reason})
        self.act(plot.pid, day, "flag_sensor", reason)

    def accept(self, plot, day, value, prior):
        gap = max(1, day - self.last_trusted[plot.pid])
        innovation = level_to_storage(value, AGENT_SY) - level_to_storage(prior, AGENT_SY)
        self.loss[plot.pid] = float(np.clip(self.loss[plot.pid] - LOSS_GAIN * innovation / gap, 0.5, 8.0))
        self.est[plot.pid] = prior + BLEND * (value - prior)
        self.last_trusted[plot.pid] = day
        self.evidence[(plot.pid, day)] = value

    def request(self, plot, day, reason):
        self.remeasure_requests.add(plot.pid)
        self.act(plot.pid, day, "remeasure", reason)

    def resolve(self, plot, day, photo, sensor):
        case = self.pending.pop(plot.pid)
        drift = self.est[plot.pid] - case["expected"]
        if case["kind"] == "sensor_photo":
            if sensor is not None and abs(photo - sensor) <= AGREE_CM:
                self.detections.append({"fault": "c_photo_misread", "pid": plot.pid, "cluster": plot.cluster, "day": day, "ref_day": case["day"], "note": "re-photo matches sensor"})
                self.act(plot.pid, day, "flag_photo")
                self.evidence[(plot.pid, case["day"])] = case["sensor"]
                return (photo + sensor) / 2
            if abs(photo - (case["photo"] + drift)) <= CONFIRM_PHOTO_CM:
                self.flag_sensor(plot, day, "re-photo confirms first photo")
                self.evidence[(plot.pid, case["day"])] = case["photo"]
            return photo
        if case["kind"] == "sensor_model" and sensor is not None and abs(photo - sensor) > SENSOR_PHOTO_CONFLICT_CM:
            self.flag_sensor(plot, day, "photo contradicts sensor")
        return photo

    def check_stuck(self, plot, day):
        history = self.sensor_history[plot.pid][-4:]
        deltas = self.expected_delta[plot.pid][-3:]
        at_range_limit = any(v <= SENSOR_RANGE_MIN_CM for _, v in history)
        if len(history) == 4 and not at_range_limit and history[0][0] == day - 3 and max(v for _, v in history) - min(v for _, v in history) <= 0.05 and sum(abs(x) for x in deltas) > 1.5:
            self.flag_sensor(plot, day, "stuck value")
            return True
        return False

    def fuse(self, plot, day, o):
        pid = plot.pid
        prior = self.est[pid]
        if pid in self.flagged and day >= self.sensor_repair_day[pid]:
            del self.flagged[pid]
            self.sensor_history[pid] = []
        sensor = o["sensor"] if pid not in self.flagged else None
        if sensor is not None:
            self.sensor_history[pid].append((day, sensor))
            if self.check_stuck(plot, day):
                sensor = None
        photo = o["photo"]
        if pid in self.pending:
            recheck = o["recheck"] if o["recheck"] is not None else photo
            if recheck is not None:
                self.accept(plot, day, self.resolve(plot, day, recheck, sensor), prior)
                return
            if day - self.pending[pid]["day"] >= 3:
                del self.pending[pid]
            else:
                self.request(plot, day, "repeat")
                return
        if sensor is not None and photo is not None:
            if abs(sensor - photo) > SENSOR_PHOTO_CONFLICT_CM:
                self.pending[pid] = {"kind": "sensor_photo", "day": day, "sensor": sensor, "photo": photo, "expected": prior}
                self.request(plot, day, "photo vs sensor")
                return
            self.accept(plot, day, (sensor + photo) / 2, prior)
        elif sensor is not None:
            if abs(sensor - prior) > SENSOR_MODEL_CONFLICT_CM:
                self.pending[pid] = {"kind": "sensor_model", "day": day, "sensor": sensor, "photo": None, "expected": prior}
                self.request(plot, day, "sensor vs model")
                return
            self.accept(plot, day, sensor, prior)
        elif photo is not None or o["recheck"] is not None:
            photo = photo if photo is not None else o["recheck"]
            if not plot.has_sensor and abs(photo - prior) > PHOTO_MODEL_CONFLICT_CM:
                self.pending[pid] = {"kind": "photo_model", "day": day, "sensor": None, "photo": photo, "expected": prior}
                self.request(plot, day, "photo vs model")
                return
            self.accept(plot, day, photo, prior)
        if pid not in self.remeasure_requests and self.should_request_stale(plot, day):
            self.request(plot, day, "stale")

    def should_request_stale(self, plot, day):
        return day - self.last_trusted[plot.pid] >= STALE_DAYS

    def awd_margin(self, plot, day):
        return AWD_MARGIN_CM

    def track_logs(self, plot, day, o):
        pid = plot.pid
        if o["logger"] is not None:
            self.last_covered[pid] = day
        if o["logger"] == "farmer" and pid in self.escalated:
            self.escalated.discard(pid)
        if day - self.last_covered[pid] >= MISSING_LOG_DAYS and pid not in self.escalated:
            self.escalated.add(pid)
            self.detections.append({"fault": "b_missing_logs", "pid": pid, "cluster": plot.cluster, "day": day, "ref_day": self.last_covered[pid] + 1, "note": ""})
            self.act(pid, day, "escalate")

    def need(self, plot, day, next_run, with_rain):
        h, streak, worst, priority = self.est[plot.pid], self.dry_streak[plot.pid], self.est[plot.pid], None
        for j in range(day, next_run + 1):
            st = plot.stage(j)
            if st in NO_DRYING_STAGES and h < WET_MARGIN_CM:
                priority = min(priority if priority is not None else 9, 0 if st == "heading" else 1)
            if st == "awd" and h < AWD_THRESHOLD_CM + self.awd_margin(plot, day):
                priority = min(priority if priority is not None else 9, 2)
            if st == "awd" and plot.poorly_drained and streak >= MAX_DRY_DAYS_POORLY_DRAINED - 1:
                priority = min(priority if priority is not None else 9, 2)
            worst = min(worst, h)
            if st == "drain" or not plot.active(j):
                break
            h = self.propagate(plot, h, j, self.forecast_rain(plot, j, day) if with_rain else 0.0)
            streak = streak + 1 if h < 0 else 0
        return priority, worst

    def plan(self, c, day):
        runs = self.known_runs(c, day)
        later = sorted(d for d in runs if d > day)
        next_run = later[0] if later else day + 7
        candidates = []
        for p in self.sc.plots:
            if p.cluster != c or not p.active(day):
                continue
            priority, worst = self.need(p, day, next_run, True)
            if priority is not None:
                candidates.append((priority, worst, p.pid))
            elif self.need(p, day, next_run, False)[0] is not None:
                self.act(p.pid, day, "hold_rain")
        candidates.sort()
        queue = [pid for _, _, pid in candidates]
        for rank, pid in enumerate(queue):
            self.act(pid, day, "irrigate" if rank < self.sc.pump_capacity else "deferred")
        return queue

    def step(self, day, obs):
        for ch in self.sc.schedule_changes:
            if ch["announced_day"] == day:
                self.detections.append({"fault": "d_pump_schedule", "pid": -1, "cluster": ch["cluster"], "day": day, "ref_day": ch["day"], "note": "announced"})
                self.act(-1, day, "replan", f"cluster {ch['cluster']}")
        for pid, o in obs.items():
            plot = self.sc.plots[pid]
            if pid not in self.est:
                self.est[pid] = 3.0
            self.fuse(plot, day, o)
            if not plot.proxy:
                self.track_logs(plot, day, o)
            else:
                self.last_covered[pid] = day if o["logger"] else self.last_covered[pid]
        orders = {}
        for c in self.sc.planned_runs:
            if day in self.known_runs(c, day):
                orders[c] = self.plan(c, day)
        return orders

    def confirm(self, day, irrigated, irrigation_mm):
        for c in self.sc.planned_runs:
            if day in self.known_runs(c, day) and day not in self.sc.actual_runs[c]:
                self.known_cancelled.add((c, day))
                self.detections.append({"fault": "d_pump_schedule", "pid": -1, "cluster": c, "day": day + 1, "ref_day": day, "note": "no pump confirmation"})
                self.act(-1, day + 1, "replan", f"cluster {c}")
        for plot in self.sc.plots:
            if not plot.active(day) or plot.pid not in self.est:
                continue
            h = FILL_LEVEL_CM if plot.pid in irrigated else self.est[plot.pid]
            nxt = self.propagate(plot, h, day, self.sc.rain[plot.site][day])
            self.expected_delta[plot.pid].append(nxt - self.est[plot.pid])
            self.est[plot.pid] = nxt
            self.dry_streak[plot.pid] = self.dry_streak[plot.pid] + 1 if nxt < 0 else 0


class OraclePolicy(AgentPolicy):
    name = "oracle"

    def reset(self, sc):
        super().reset(sc)
        self.loss = {p.pid: p.percolation + p.seepage for p in sc.plots}

    def propagate(self, plot, h, day, rain):
        flux = rain - crop_coefficient(plot.k(day)) * self.sc.et0[plot.site][day] - self.loss[plot.pid]
        return step_level(h, flux, plot.sy)

    def forecast_rain(self, plot, day, origin):
        return self.sc.rain[plot.site][day]

    def fuse(self, plot, day, o):
        self.est[plot.pid] = self.truth_view[plot.pid, day]
        self.evidence[(plot.pid, day)] = self.est[plot.pid]

    def track_logs(self, plot, day, o):
        pass


class PlannerOnlyPolicy(AgentPolicy):
    name = "planner_only"

    def fuse(self, plot, day, o):
        value = o["photo"] if o["photo"] is not None else o["sensor"]
        if value is not None:
            self.est[plot.pid] = value
            self.evidence[(plot.pid, day)] = value

    def track_logs(self, plot, day, o):
        pass


TUBE_MIN_CM = -25.0


class ChecklistPolicy(PolicyBase):
    name = "checklist"
    walk_every = "pump"
    trigger_cm = -5.0
    wet_trigger_cm = 3.0

    def reset(self, sc):
        super().reset(sc)
        self.last_report = {}
        self.walks = 0

    def walk_day(self, plot, day):
        if self.walk_every == "pump":
            return day in self.sc.actual_runs[plot.cluster]
        return plot.k(day) % self.walk_every == 0

    def officer_reading(self, plot, day):
        value = self.truth_view[plot.pid, day] + self.sc.noise["rephoto"][plot.pid, day]
        return round(float(np.clip(value, TUBE_MIN_CM, 15)), 1)

    def step(self, day, obs):
        for pid, o in obs.items():
            plot = self.sc.plots[pid]
            if self.walk_day(plot, day):
                value = self.officer_reading(plot, day)
                self.walks += 1
                self.act(pid, day, "officer_walk")
            else:
                value = o["photo"] if o["photo"] is not None else o["sensor"]
            if value is not None:
                self.last_report[pid] = value
                self.evidence[(pid, day)] = value
        orders = {}
        for c, runs in self.sc.actual_runs.items():
            if day not in runs:
                continue
            candidates = []
            for p in self.sc.plots:
                if p.cluster != c or not p.active(day):
                    continue
                st, last = p.stage(day), self.last_report.get(p.pid)
                if st in NO_DRYING_STAGES and (last is None or last < self.wet_trigger_cm):
                    candidates.append((0 if st == "heading" else 1, last if last is not None else -99, p.pid))
                elif st == "awd" and (last is None or last <= self.trigger_cm):
                    candidates.append((2, last if last is not None else -99, p.pid))
            candidates.sort()
            queue = [pid for _, _, pid in candidates]
            for p in self.sc.plots:
                spare = len(queue) < self.sc.pump_capacity
                if spare and p.cluster == c and p.pid not in queue and p.active(day) and p.stage(day) in NO_DRYING_STAGES:
                    queue.append(p.pid)
            for pid in queue[:self.sc.pump_capacity]:
                self.act(pid, day, "irrigate")
            orders[c] = queue
        return orders


class AgentRiskPolicy(AgentPolicy):
    name = "agent_risk"
    max_stale_days = 3
    risk_band_cm = 7.0
    lookahead_days = 2
    batch_before_run = True
    margin_only_when_uncertain = True
    uncertain_after_days = 1
    certain_margin_cm = 1.0

    def next_known_run(self, plot, day):
        later = sorted(d for d in self.known_runs(plot.cluster, day) if d > day)
        return later[0] if later else None

    def sensitive_soon(self, plot, day):
        return any(plot.stage(day + j) in NO_DRYING_STAGES for j in range(self.lookahead_days + 1))

    def near_threshold(self, plot):
        return self.est[plot.pid] < AWD_THRESHOLD_CM + self.risk_band_cm

    def long_dry_soil(self, plot):
        return plot.poorly_drained and self.dry_streak[plot.pid] >= MAX_DRY_DAYS_POORLY_DRAINED - 3

    def should_request_stale(self, plot, day):
        age = day - self.last_trusted[plot.pid]
        if age < STALE_DAYS:
            return False
        if age >= self.max_stale_days:
            return True
        risky = self.sensitive_soon(plot, day) or self.near_threshold(plot) or self.long_dry_soil(plot)
        if not risky:
            return False
        if not self.batch_before_run:
            return True
        run = self.next_known_run(plot, day)
        return run is None or run - day <= 1 or self.sensitive_soon(plot, day)

    def awd_margin(self, plot, day):
        if not self.margin_only_when_uncertain:
            return AWD_MARGIN_CM
        uncertain = day - self.last_trusted[plot.pid] >= self.uncertain_after_days
        sensitive = self.sensitive_soon(plot, day) or self.long_dry_soil(plot)
        return AWD_MARGIN_CM if uncertain and sensitive else self.certain_margin_cm
