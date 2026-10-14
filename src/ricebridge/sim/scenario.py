from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from weather import load_weather

N_DAYS = 121
SEASON_DAYS = 105
PLOTS_PER_CLUSTER = 6
CLUSTER_SITES = ["an_giang", "an_giang", "an_giang", "can_tho", "can_tho"]
CLUSTER_SOWING_DAY = [0, 4, 8, 12, 16]
PUMP_CAPACITY = 4
PUMP_WEEKDAYS = {0: "A", 3: "B"}
FILL_LEVEL_CM = 5.0
BUND_CM = 15.0
AWD_THRESHOLD_CM = -15.0
MAX_DRY_DAYS_POORLY_DRAINED = 10
POORLY_DRAINED_PERC_MM = 2.0

KC_INI, KC_MID, KC_END = 1.05, 1.20, 0.90
NO_DRYING_STAGES = {"establishment", "topdress", "heading"}

PERCOLATION_RANGE_MM = (1.0, 5.0)
SEEPAGE_RANGE_MM = (0.5, 1.5)
SPECIFIC_YIELD_RANGE = (0.20, 0.30)
SENSOR_PLOTS_PER_CLUSTER = 2
SENSOR_NOISE_CM = 0.7
PHOTO_NOISE_CM = 1.0
FARMER_LOG_RATE = 0.85
PHOTO_RATE = 0.5
REMEASURE_COMPLIANCE = 0.9
SENSOR_FAULT_RATE = 0.5
MISREAD_RATE = 0.08
LOG_GAPS_PER_CLUSTER = 2
SCHEDULE_CHANGES_PER_CLUSTER = 2


def stage(k):
    if k < 0 or k >= SEASON_DAYS:
        return "off"
    if k < 20:
        return "establishment"
    if k < 25 or 40 <= k < 45:
        return "topdress"
    if 60 <= k < 80:
        return "heading"
    if k >= 95:
        return "drain"
    return "awd"


def crop_coefficient(k):
    if k < 20:
        return KC_INI
    if k < 40:
        return KC_INI + (KC_MID - KC_INI) * (k - 20) / 20
    if k < 80:
        return KC_MID
    return KC_MID + (KC_END - KC_MID) * (k - 80) / (SEASON_DAYS - 1 - 80)


def level_to_storage(h, sy):
    return 10.0 * h if h >= 0 else 10.0 * sy * h


def storage_to_level(s, sy):
    return s / 10.0 if s >= 0 else s / (10.0 * sy)


def step_level(h, flux_mm, sy):
    level = storage_to_level(level_to_storage(h, sy) + flux_mm, sy)
    return float(np.clip(level, -40.0, BUND_CM))


@dataclass
class Plot:
    pid: int
    cluster: int
    index: int
    site: str
    sowing_day: int
    percolation: float
    seepage: float
    sy: float
    has_sensor: bool
    proxy: bool
    slot: str

    @property
    def poorly_drained(self):
        return self.percolation < POORLY_DRAINED_PERC_MM

    def k(self, day):
        return day - self.sowing_day

    def stage(self, day):
        return stage(self.k(day))

    def active(self, day):
        return 0 <= self.k(day) < SEASON_DAYS


@dataclass
class Scenario:
    seed: int
    dates: pd.DatetimeIndex
    rain: dict
    et0: dict
    plots: list
    noise: dict
    sensor_faults: dict
    misread_offset: np.ndarray
    farmer_absent: np.ndarray
    log_gaps: list
    planned_runs: dict
    actual_runs: dict
    schedule_changes: list
    forecast_factor: np.ndarray
    labels: list = field(default_factory=list)
    pump_capacity: int = PUMP_CAPACITY


def weekly_runs(dates, start, end):
    return {d: PUMP_WEEKDAYS[dates[d].weekday()] for d in range(start, end) if dates[d].weekday() in PUMP_WEEKDAYS}


def build_scenario(seed, pump_capacity=PUMP_CAPACITY):
    rng = np.random.default_rng(seed)
    weather = load_weather()
    dates = pd.DatetimeIndex(weather["an_giang"]["date"])
    rain = {s: w["rain_mm"].to_numpy() for s, w in weather.items()}
    et0 = {s: w["et0_mm"].to_numpy() for s, w in weather.items()}

    plots = []
    for c, site in enumerate(CLUSTER_SITES):
        order = rng.permutation(PLOTS_PER_CLUSTER)
        sensor_idx = set(order[:SENSOR_PLOTS_PER_CLUSTER])
        proxy_idx = order[SENSOR_PLOTS_PER_CLUSTER]
        for i in range(PLOTS_PER_CLUSTER):
            plots.append(
                Plot(
                    pid=len(plots),
                    cluster=c,
                    index=i,
                    site=site,
                    sowing_day=CLUSTER_SOWING_DAY[c],
                    percolation=rng.uniform(*PERCOLATION_RANGE_MM),
                    seepage=rng.uniform(*SEEPAGE_RANGE_MM),
                    sy=rng.uniform(*SPECIFIC_YIELD_RANGE),
                    has_sensor=i in sensor_idx,
                    proxy=i == proxy_idx,
                    slot="A" if i < PLOTS_PER_CLUSTER // 2 else "B",
                )
            )

    n = len(plots)
    shape = (n, N_DAYS)
    noise = {
        "sensor": rng.normal(0, SENSOR_NOISE_CM, shape),
        "photo": rng.normal(0, PHOTO_NOISE_CM, shape),
        "rephoto": rng.normal(0, PHOTO_NOISE_CM, shape),
        "log": rng.random(shape) < FARMER_LOG_RATE,
        "photo_taken": rng.random(shape) < PHOTO_RATE,
        "comply": rng.random(shape) < REMEASURE_COMPLIANCE,
    }
    forecast_factor = rng.uniform(0.5, 1.5, (len(CLUSTER_SITES), N_DAYS))

    labels = []
    sensor_faults = {}
    for p in plots:
        if p.has_sensor and rng.random() < SENSOR_FAULT_RATE:
            onset = p.sowing_day + int(rng.integers(15, 86))
            kind = "drift" if rng.random() < 0.5 else "stuck"
            rate = float(rng.choice([-1, 1]) * rng.uniform(0.6, 1.2)) if kind == "drift" else 0.0
            sensor_faults[p.pid] = {"onset": onset, "kind": kind, "rate": rate}
            labels.append({"fault": "a_sensor", "pid": p.pid, "cluster": p.cluster, "day": onset, "end_day": N_DAYS - 1, "detail": f"{kind} {rate:+.2f} cm/ngay" if kind == "drift" else kind})

    misread_offset = np.zeros(shape)
    for p in plots:
        if not p.has_sensor:
            continue
        healthy_until = sensor_faults[p.pid]["onset"] if p.pid in sensor_faults else N_DAYS
        for d in range(N_DAYS):
            photo_day = p.active(d) and noise["log"][p.pid, d] and noise["photo_taken"][p.pid, d]
            if photo_day and d < healthy_until and rng.random() < MISREAD_RATE:
                misread_offset[p.pid, d] = float(rng.choice([-1, 1]) * rng.uniform(6, 12))
                labels.append({"fault": "c_photo_misread", "pid": p.pid, "cluster": p.cluster, "day": d, "end_day": d, "detail": f"{misread_offset[p.pid, d]:+.1f} cm"})

    farmer_absent = np.zeros(shape, dtype=bool)
    for c in range(len(CLUSTER_SITES)):
        candidates = [p for p in plots if p.cluster == c and not p.proxy]
        for p in rng.choice(candidates, LOG_GAPS_PER_CLUSTER, replace=False):
            start = p.sowing_day + int(rng.integers(10, 91))
            length = int(rng.integers(3, 8))
            farmer_absent[p.pid, start:start + length] = True

    log_gaps = []
    for p in plots:
        if p.proxy:
            continue
        logged = [noise["log"][p.pid, d] and not farmer_absent[p.pid, d] for d in range(N_DAYS)]
        run_start = None
        for d in range(p.sowing_day, p.sowing_day + SEASON_DAYS + 1):
            missing = d < p.sowing_day + SEASON_DAYS and not logged[d]
            if missing and run_start is None:
                run_start = d
            if not missing and run_start is not None:
                if d - run_start >= 3:
                    injected = bool(farmer_absent[p.pid, run_start:d].any())
                    log_gaps.append({"pid": p.pid, "start": run_start, "end": d - 1, "injected": injected})
                    labels.append({"fault": "b_missing_logs", "pid": p.pid, "cluster": p.cluster, "day": run_start, "end_day": d - 1, "detail": "injected" if injected else "natural"})
                run_start = None

    planned_runs, actual_runs, schedule_changes = {}, {}, []
    for c in range(len(CLUSTER_SITES)):
        start = CLUSTER_SOWING_DAY[c]
        planned = weekly_runs(dates, start, start + SEASON_DAYS)
        actual = dict(planned)
        eligible = [d for d in planned if start + 15 <= d <= start + 90]
        for d in sorted(rng.choice(eligible, SCHEDULE_CHANGES_PER_CLUSTER, replace=False)):
            d = int(d)
            if rng.random() < 0.5:
                new_day = d + int(rng.integers(1, 3))
                while new_day in actual:
                    new_day += 1
                actual[new_day] = actual.pop(d)
                change = {"cluster": c, "day": d, "new_day": new_day, "announced_day": d - 1, "kind": "moved_announced"}
            else:
                actual.pop(d)
                change = {"cluster": c, "day": d, "new_day": None, "announced_day": None, "kind": "cancelled_unannounced"}
            schedule_changes.append(change)
            labels.append({"fault": "d_pump_schedule", "pid": -1, "cluster": c, "day": d, "end_day": d, "detail": change["kind"]})
        planned_runs[c] = planned
        actual_runs[c] = actual

    for p in plots:
        if p.proxy:
            labels.append({"fault": "e_proxy_logging", "pid": p.pid, "cluster": p.cluster, "day": p.sowing_day, "end_day": p.sowing_day + SEASON_DAYS - 1, "detail": "not a fault"})

    return Scenario(seed, dates, rain, et0, plots, noise, sensor_faults, misread_offset, farmer_absent, log_gaps, planned_runs, actual_runs, schedule_changes, forecast_factor, labels, pump_capacity)
