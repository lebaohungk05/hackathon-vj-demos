import argparse
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from consistency import check_photo
from gauge_reader import MODEL, read_gauge_photo

HERE = Path(__file__).resolve().parent
TESTSET = HERE / "testset"
OUT = HERE / "out"

HERO_CONTEXT = {"sensor_cm": 2.0, "water_balance_cm": 2.0, "latest_rain_at": "2026-02-24T19:00:00", "submitted_at": "2026-02-25T07:10:00"}


def run_one(row, replay):
    started = time.perf_counter()
    result = read_gauge_photo(TESTSET / row["file"], replay=replay)
    wall = round(time.perf_counter() - started, 2)
    err = None if result["reading_cm"] is None else round(result["reading_cm"] - row["truth_cm"], 2)
    return {**row, **result, "error_cm": err, "wall_seconds": wall, "exif_matches_truth": result["captured_at"] == row["captured_at"]}


def summarize(rows):
    errs = [abs(r["error_cm"]) for r in rows if r["error_cm"] is not None]
    llm_times = [r["llm_seconds"] for r in rows if r.get("llm_seconds")]
    return {
        "n_images": len(rows),
        "n_read": len(errs),
        "n_failed": len(rows) - len(errs),
        "mae_cm": round(statistics.mean(errs), 2) if errs else None,
        "max_abs_error_cm": round(max(errs), 2) if errs else None,
        "pct_within_2cm": round(100 * sum(e <= 2 for e in errs) / len(rows), 1),
        "pct_within_1cm": round(100 * sum(e <= 1 for e in errs) / len(rows), 1),
        "llm_seconds_per_image_mean": round(statistics.mean(llm_times), 2) if llm_times else None,
        "llm_seconds_per_image_median": round(statistics.median(llm_times), 2) if llm_times else None,
        "llm_seconds_per_image_max": round(max(llm_times), 2) if llm_times else None,
        "exif_capture_time_correct": sum(r["exif_matches_truth"] for r in rows),
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Evaluate the gauge reader on the synthetic test set")
    p.add_argument("--replay", action="store_true", help="use cached readings only")
    p.add_argument("--workers", type=int, default=4)
    a = p.parse_args()
    truth = json.loads((TESTSET / "ground_truth.json").read_text(encoding="utf-8"))["images"]
    started = time.perf_counter()
    with ThreadPoolExecutor(a.workers) as pool:
        rows = list(pool.map(lambda r: run_one(r, a.replay), truth))
    total = round(time.perf_counter() - started, 1)
    hero = next(r for r in rows if r["hero"])
    hero_check = check_photo(hero["reading_cm"], hero["captured_at"], photo_confidence=hero["confidence"], **HERO_CONTEXT)
    metrics = {
        "model": MODEL,
        "dataset": "SYNTHETIC rendered gauge photos (make_testset.py), not real field photos",
        "mode": "replay" if a.replay else "live",
        "workers": a.workers,
        "total_wall_seconds": total,
        **summarize(rows),
        "hero": {"file": hero["file"], "truth_cm": hero["truth_cm"], "reading_cm": hero["reading_cm"], "captured_at": hero["captured_at"], "context": HERO_CONTEXT, "consistency": hero_check},
        "per_image": rows,
    }
    OUT.mkdir(exist_ok=True)
    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    for r in rows:
        shown = "NA" if r["reading_cm"] is None else f"{r['reading_cm']:+.1f}"
        print(f"{r['file']:24} truth {r['truth_cm']:+6.1f}  read {shown:>6}  err {r['error_cm']}  {r['source']}  {r.get('llm_seconds')}s")
    print(json.dumps({k: v for k, v in metrics.items() if k != "per_image"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
