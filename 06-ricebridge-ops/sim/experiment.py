import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from policies import AgentPolicy, AgentRiskPolicy, BaselinePolicy, ChecklistPolicy, OraclePolicy, PlannerOnlyPolicy
from scenario import AWD_THRESHOLD_CM, MAX_DRY_DAYS_POORLY_DRAINED, N_DAYS, SEASON_DAYS, build_scenario
from simulate import simulate

DEV_SEEDS = list(range(0, 10))
TEST_SEEDS = list(range(1000, 1020))
DRY_CM = -5.0
GRACE_DAYS = 2
VALID_READING_CM = 3.0
EVIDENCE_BLOCK_DAYS = 3
OUT = Path(__file__).parent / "out"
POLICIES = (AgentPolicy, AgentRiskPolicy, BaselinePolicy, ChecklistPolicy, PlannerOnlyPolicy, OraclePolicy)


def water_metrics(sc, truth):
    awd_violation = heading_dry = topdress_dry = awd_drying = awd_safe_drying = awd_deep = 0
    for p in sc.plots:
        below, dry = 0, 0
        for d in range(p.sowing_day, p.sowing_day + SEASON_DAYS):
            h, st = truth[p.pid, d], p.stage(d)
            below = below + 1 if h < AWD_THRESHOLD_CM else 0
            dry = dry + 1 if h < 0 else 0
            if st == "awd":
                awd_drying += h < 0
                too_deep = below > GRACE_DAYS
                too_long = p.poorly_drained and dry > MAX_DRY_DAYS_POORLY_DRAINED
                awd_violation += too_deep or too_long
                awd_safe_drying += h < 0 and not (too_deep or too_long)
                awd_deep += h < AWD_THRESHOLD_CM
            heading_dry += st == "heading" and h < DRY_CM
            topdress_dry += st == "topdress" and h < DRY_CM
    return {
        "awd_violation_plot_days": int(awd_violation),
        "heading_dry_plot_days": int(heading_dry),
        "topdress_dry_plot_days": int(topdress_dry),
        "awd_drying_plot_days": int(awd_drying),
        "awd_safe_drying_plot_days": int(awd_safe_drying),
        "awd_deep_plot_days": int(awd_deep),
    }


def evidence_completeness(sc, truth, evidence):
    blocks = valid = 0
    for p in sc.plots:
        for start in range(p.sowing_day, p.sowing_day + SEASON_DAYS, EVIDENCE_BLOCK_DAYS):
            blocks += 1
            days = range(start, min(start + EVIDENCE_BLOCK_DAYS, p.sowing_day + SEASON_DAYS))
            valid += any((p.pid, d) in evidence and abs(evidence[(p.pid, d)] - truth[p.pid, d]) <= VALID_READING_CM for d in days)
    return valid / blocks


def score(events, detections, match):
    matched, tp, ttd = set(), 0, []
    for det in detections:
        hit = next((i for i, ev in enumerate(events) if i not in matched and match(ev, det)), None)
        if hit is None:
            continue
        matched.add(hit)
        tp += 1
        ttd.append(det["day"] - events[hit]["t0"])
    fp = sum(1 for det in detections if not any(match(ev, det) for ev in events))
    return {
        "events": len(events),
        "detected": tp,
        "false_alarms": fp,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / len(events) if events else None,
        "mean_ttd_days": float(np.mean(ttd)) if ttd else None,
    }


def detection_metrics(sc, detections):
    by_type = lambda f: [d for d in detections if d["fault"] == f]
    proxy = {p.pid for p in sc.plots if p.proxy}
    sensor_events = [{"pid": pid, "t0": f["onset"]} for pid, f in sc.sensor_faults.items()]
    misread_events = [{"pid": l["pid"], "t0": l["day"]} for l in sc.labels if l["fault"] == "c_photo_misread"]
    injected_gaps = [{"pid": g["pid"], "t0": g["start"], "end": g["end"]} for g in sc.log_gaps if g["injected"]]
    all_gaps = [{"pid": g["pid"], "t0": g["start"], "end": g["end"]} for g in sc.log_gaps]
    schedule_events = [{"cluster": ch["cluster"], "t0": ch["day"]} for ch in sc.schedule_changes]
    gap_dets = [d for d in by_type("b_missing_logs") if d["pid"] not in proxy]
    gap_match = lambda ev, det: ev["pid"] == det["pid"] and ev["t0"] <= det["day"] <= ev["end"]
    gaps = score(injected_gaps, gap_dets, gap_match)
    gaps["false_alarms"] = sum(1 for det in gap_dets if not any(gap_match(ev, det) for ev in all_gaps))
    gaps["precision"] = (len(gap_dets) - gaps["false_alarms"]) / len(gap_dets) if gap_dets else None
    return {
        "a_sensor": score(sensor_events, by_type("a_sensor"), lambda ev, det: ev["pid"] == det["pid"] and det["day"] >= ev["t0"]),
        "b_missing_logs": gaps,
        "c_photo_misread": score(misread_events, by_type("c_photo_misread"), lambda ev, det: ev["pid"] == det["pid"] and ev["t0"] == det["ref_day"]),
        "d_pump_schedule": score(schedule_events, by_type("d_pump_schedule"), lambda ev, det: ev["cluster"] == det["cluster"] and ev["t0"] == det["ref_day"]),
        "e_proxy_false_flags_agent": sum(1 for d in by_type("b_missing_logs") if d["pid"] in proxy),
        "e_proxy_false_flags_naive_farmer_only_rule": len(proxy),
    }


def run_one(seed, policy_cls, **scenario_args):
    sc = build_scenario(seed, **scenario_args)
    policy = policy_cls()
    result = simulate(sc, policy)
    truth = result["truth"]
    irrigation = result["irrigation_mm"]
    actions = pd.DataFrame(policy.actions, columns=["pid", "day", "action", "note"])
    season_plot_weeks = len(sc.plots) * SEASON_DAYS / 7
    metrics = water_metrics(sc, truth)
    metrics.update(
        {
            "evidence_completeness_pct": 100 * evidence_completeness(sc, truth, policy.evidence),
            "plot_irrigations": int((irrigation > 0).sum()),
            "pump_days_used": int(len({(sc.plots[i].cluster, d) for i, d in zip(*np.nonzero(irrigation > 0))})),
            "water_applied_mm_per_plot": float(irrigation.sum() / len(sc.plots)),
            "remeasure_requests_per_plot_week": float((actions["action"] == "remeasure").sum() / season_plot_weeks),
            "officer_visits_per_plot_week": float((actions["action"] == "officer_walk").sum() / season_plot_weeks),
            "detection": detection_metrics(sc, policy.detections),
        }
    )
    return sc, policy, result, metrics


def flatten(d, prefix=""):
    flat = {}
    for k, v in d.items():
        if isinstance(v, dict):
            flat.update(flatten(v, f"{prefix}{k}."))
        else:
            flat[f"{prefix}{k}"] = v
    return flat


def summarize(rows):
    frame = pd.DataFrame(rows)
    summary = {}
    for col in frame.columns:
        values = pd.to_numeric(frame[col], errors="coerce").dropna()
        if len(values):
            summary[col] = {"mean": round(float(values.mean()), 3), "min": round(float(values.min()), 3), "max": round(float(values.max()), 3), "n": int(len(values))}
    return summary


def save_ground_truth(out, seed, sc, results):
    rows = []
    for name, (policy, result) in results.items():
        truth = result["truth"]
        for p in sc.plots:
            for d in range(p.sowing_day, p.sowing_day + SEASON_DAYS):
                rows.append({"seed": seed, "policy": name, "cluster": p.cluster, "plot": p.index, "pid": p.pid, "day": d, "date": sc.dates[d].date(), "season_day": p.k(d), "stage": p.stage(d), "true_level_cm": round(float(truth[p.pid, d]), 2), "irrigation_mm": round(float(result["irrigation_mm"][p.pid, d]), 1), "rain_mm": sc.rain[p.site][d], "et0_mm": sc.et0[p.site][d]})
    plots = pd.DataFrame([{**vars(p), "poorly_drained": p.poorly_drained} for p in sc.plots]).assign(seed=seed)
    labels = pd.DataFrame(sc.labels).assign(seed=seed)
    obs = pd.concat([r["observations"].assign(policy=n, seed=seed) for n, (_, r) in results.items()])
    actions = pd.concat([pd.DataFrame(pol.actions).assign(policy=n, seed=seed) for n, (pol, _) in results.items()])
    return pd.DataFrame(rows), plots, labels, obs, actions


def main(split):
    seeds = TEST_SEEDS if split == "test" else DEV_SEEDS
    out = OUT / split
    out.mkdir(parents=True, exist_ok=True)
    per_seed = {cls.name: [] for cls in POLICIES}
    tables = {k: [] for k in ["ground_truth", "plots", "labels", "observations", "actions"]}
    for seed in seeds:
        results = {}
        for policy_cls in POLICIES:
            sc, policy, result, metrics = run_one(seed, policy_cls)
            per_seed[policy.name].append({"seed": seed, **flatten(metrics)})
            results[policy.name] = (policy, result)
        for key, frame in zip(tables, save_ground_truth(out, seed, sc, results)):
            tables[key].append(frame)
    for key, frames in tables.items():
        pd.concat(frames).to_csv(out / f"{key}.csv", index=False)
    pd.concat([pd.DataFrame(rows).assign(policy=name) for name, rows in per_seed.items()]).to_csv(out / "metrics_per_seed.csv", index=False)
    results = {"split": split, "seeds": seeds, "summary": {name: summarize(rows) for name, rows in per_seed.items()}}
    (out / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    return results


if __name__ == "__main__":
    res = main(sys.argv[1] if len(sys.argv) > 1 else "dev")
    for name in res["summary"]:
        print(f"== {name}")
        for key, v in res["summary"][name].items():
            if key != "seed":
                print(f"  {key}: {v['mean']} [{v['min']}, {v['max']}]")
