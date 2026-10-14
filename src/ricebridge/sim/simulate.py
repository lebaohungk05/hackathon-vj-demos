import numpy as np
import pandas as pd

from scenario import FILL_LEVEL_CM, N_DAYS, crop_coefficient, level_to_storage, step_level

INITIAL_LEVEL_CM = 3.0
SENSOR_MIN_CM = -30.0
TUBE_MIN_CM = -25.0


def sensor_fault_active(sc, policy, pid, day):
    fault = sc.sensor_faults.get(pid)
    if fault is None or day < fault["onset"]:
        return False
    repair = policy.sensor_repair_day.get(pid)
    return not (repair is not None and fault["onset"] <= repair <= day)


def read_sensor(sc, policy, plot, day, truth_matrix):
    truth = truth_matrix[plot.pid, day]
    fault = sc.sensor_faults.get(plot.pid)
    noise = sc.noise["sensor"][plot.pid, day]
    if sensor_fault_active(sc, policy, plot.pid, day):
        if fault["kind"] == "stuck":
            return round(truth_matrix[plot.pid, fault["onset"]] + sc.noise["sensor"][plot.pid, fault["onset"]], 1)
        return round(truth + noise + fault["rate"] * (day - fault["onset"]), 1)
    return round(truth + noise, 1)


def observe(sc, policy, plot, day, truth_matrix, requested):
    pid = plot.pid
    truth = truth_matrix[pid, day]
    obs = {"pid": pid, "day": day, "sensor": None, "photo": None, "logger": None, "covers_prev": False, "recheck": None}
    if plot.has_sensor:
        obs["sensor"] = float(np.clip(read_sensor(sc, policy, plot, day, truth_matrix), SENSOR_MIN_CM, 15))
    farmer_present = not plot.proxy and not sc.farmer_absent[pid, day]
    if farmer_present and sc.noise["log"][pid, day]:
        obs["logger"] = "farmer"
        if sc.noise["photo_taken"][pid, day]:
            obs["photo"] = truth + sc.noise["photo"][pid, day] + sc.misread_offset[pid, day]
    if plot.proxy and plot.k(day) % 2 == 0:
        obs["logger"], obs["covers_prev"] = "htx_proxy", True
        obs["photo"] = truth + sc.noise["photo"][pid, day]
    if not farmer_present and not plot.proxy and pid in policy.escalated:
        obs["logger"] = "htx_escalation"
        obs["photo"] = truth + sc.noise["photo"][pid, day]
    if requested:
        responder = plot.proxy or pid in policy.escalated or (farmer_present and sc.noise["comply"][pid, day])
        if responder:
            obs["recheck"] = truth + sc.noise["rephoto"][pid, day]
            obs["logger"] = obs["logger"] or ("htx_proxy" if plot.proxy else "farmer")
    for key in ("photo", "recheck"):
        if obs[key] is not None:
            obs[key] = round(float(np.clip(obs[key], TUBE_MIN_CM, 15)), 1)
    return obs


def simulate(sc, policy):
    n = len(sc.plots)
    truth = np.full((n, N_DAYS + 1), np.nan)
    irrigation_mm = np.zeros((n, N_DAYS))
    policy.reset(sc)
    policy.truth_view = truth
    observations, runs = [], []
    for day in range(N_DAYS):
        requested = set(policy.remeasure_requests)
        policy.remeasure_requests = set()
        day_obs = {}
        for plot in sc.plots:
            if plot.k(day) == 0:
                truth[plot.pid, day] = INITIAL_LEVEL_CM
            if plot.active(day):
                day_obs[plot.pid] = observe(sc, policy, plot, day, truth, plot.pid in requested)
        observations.extend(day_obs.values())
        orders = policy.step(day, day_obs)
        executed = []
        for c in range(len(sc.actual_runs)):
            if day in sc.actual_runs[c]:
                queue = [pid for pid in orders.get(c, []) if sc.plots[pid].active(day)]
                executed.extend(queue[:sc.pump_capacity])
                runs.append({"cluster": c, "day": day, "label": sc.actual_runs[c][day], "served": len(queue[:sc.pump_capacity])})
        for plot in sc.plots:
            if not plot.active(day):
                continue
            h = truth[plot.pid, day]
            if plot.pid in executed and h < FILL_LEVEL_CM:
                irrigation_mm[plot.pid, day] = level_to_storage(FILL_LEVEL_CM, plot.sy) - level_to_storage(h, plot.sy)
                h = FILL_LEVEL_CM
            k = plot.k(day)
            flux = sc.rain[plot.site][day] - crop_coefficient(k) * sc.et0[plot.site][day] - plot.percolation - plot.seepage
            truth[plot.pid, day + 1] = step_level(h, flux, plot.sy)
        policy.confirm(day, [pid for pid in executed if irrigation_mm[pid, day] > 0], irrigation_mm[:, day])
    return {
        "truth": truth[:, :N_DAYS],
        "irrigation_mm": irrigation_mm,
        "observations": pd.DataFrame(observations),
        "runs": pd.DataFrame(runs),
    }
