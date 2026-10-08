import argparse
import json
import pathlib
import random
import time

from playwright.sync_api import sync_playwright

from agent import run_with_repair
from flows import BLOCKING_RULE, FLOWS, render, sample_defects

ROOT = pathlib.Path(__file__).resolve().parent
AXE = ROOT / "vendor" / "axe.min.js"
SPLITS = {"dev": (range(0, 40), range(3000, 3010)), "test": (range(1000, 1060), range(5000, 5020))}


def build_variants(split, out):
    defect_seeds, clean_seeds = SPLITS[split]
    variants = []
    for seed in list(defect_seeds) + list(clean_seeds):
        rng = random.Random(seed)
        flow = rng.choice(sorted(FLOWS))
        clean = seed in clean_seeds
        defects = [] if clean else sample_defects(flow, rng, rng.randint(1, 3))
        name = f"{split}_{seed}_{flow}{'_clean' if clean else ''}"
        path = out / "pages" / f"{name}.html"
        path.write_text(render(flow, seed, defects), encoding="utf-8")
        variants.append({"name": name, "seed": seed, "flow": flow, "clean": clean, "defects": defects, "path": str(path)})
    (out / "labels.json").write_text(json.dumps({"blocking_rule": BLOCKING_RULE, "variants": variants},
                                                ensure_ascii=False, indent=1), encoding="utf-8")
    return variants


def run_axe(page, variant):
    uri = pathlib.Path(variant["path"]).as_uri()
    per_step = []
    for k in range(1, len(FLOWS[variant["flow"]]["steps"]) + 1):
        page.goto("about:blank")
        page.goto(f"{uri}#audit={k}")
        page.add_script_tag(path=str(AXE))
        res = page.evaluate("""async()=>{const r=await axe.run(document,{resultTypes:['violations']});
            return r.violations.flatMap(v=>v.nodes.map(n=>{const el=document.querySelector(n.target[0]);
            const d=el&&el.closest('[data-defect]');return {rule:v.id,impact:v.impact,defect:d?d.dataset.defect:null};}));}""")
        per_step.append({"step": k, "violations": res})
    return per_step


def first_blocking_step(variant):
    steps = [d["step"] for d in variant["defects"] if d["blocking"]]
    return min(steps) if steps else None


def score(variants, results):
    m = {"agent": {"tp": 0, "fp": 0, "fn": 0, "tp_first_pass": 0}, "axe": {"tp": 0, "fp": 0, "fn": 0, "nonblocking_flagged": 0}}
    loc = {"agent": 0, "axe": 0, "n": 0}
    blocked_before = completed_before = completed_after = handoff = unresolved = 0
    clean = {"n": 0, "agent_breakpoints": 0, "agent_completed": 0, "axe_violation_nodes": 0, "axe_pages_flagged": 0}
    n_defect_variants = n_blocking_defects = n_nonblocking_defects = 0
    for v in variants:
        r = results[v["name"]]
        rounds = r["agent"]["rounds"]
        preds = {(rd["breakpoint"]["step"], s) for rd in rounds if rd["breakpoint"] for s in rd["breakpoint"]["suspects"]}
        first_preds = {(rounds[0]["breakpoint"]["step"], s) for s in rounds[0]["breakpoint"]["suspects"]} if rounds[0]["breakpoint"] else set()
        axe_nodes = [x for st in r["axe"] for x in st["violations"]]
        if v["clean"]:
            clean["n"] += 1
            clean["agent_breakpoints"] += len(preds)
            clean["agent_completed"] += int(rounds[0]["completed"])
            clean["axe_violation_nodes"] += len(axe_nodes)
            clean["axe_pages_flagged"] += sum(1 for st in r["axe"] if st["violations"])
            m["agent"]["fp"] += len(preds)
            m["axe"]["fp"] += len(axe_nodes)
            continue
        n_defect_variants += 1
        blocking = [d for d in v["defects"] if d["blocking"]]
        n_blocking_defects += len(blocking)
        n_nonblocking_defects += len(v["defects"]) - len(blocking)
        keys = {(d["step"], d["detect_key"]) for d in blocking}
        m["agent"]["tp"] += sum(1 for d in blocking if (d["step"], d["detect_key"]) in preds)
        m["agent"]["tp_first_pass"] += sum(1 for d in blocking if (d["step"], d["detect_key"]) in first_preds)
        m["agent"]["fn"] += sum(1 for d in blocking if (d["step"], d["detect_key"]) not in preds)
        m["agent"]["fp"] += len(preds - keys)
        flagged = {x["defect"] for x in axe_nodes if x["defect"]}
        by_id = {d["id"]: d for d in v["defects"]}
        m["axe"]["tp"] += sum(1 for d in blocking if d["id"] in flagged)
        m["axe"]["fn"] += sum(1 for d in blocking if d["id"] not in flagged)
        m["axe"]["nonblocking_flagged"] += sum(1 for i in flagged if not by_id[i]["blocking"])
        m["axe"]["fp"] += sum(1 for i in flagged if not by_id[i]["blocking"]) + sum(1 for x in axe_nodes if not x["defect"])
        fb = first_blocking_step(v)
        if fb is not None:
            blocked_before += int(not rounds[0]["completed"])
            loc["n"] += 1
            bp = rounds[0]["breakpoint"]
            loc["agent"] += int(bool(bp) and bp["step"] == fb)
            axe_first = next((st["step"] for st in r["axe"] if st["violations"]), None)
            loc["axe"] += int(axe_first == fb)
        completed_before += int(rounds[0]["completed"])
        completed_after += int(r["agent"]["completed_after"])
        handoff += int(r["agent"]["handoff"])
        unresolved += int(not r["agent"]["completed_after"] and not r["agent"]["handoff"])

    def pr(x):
        p = x["tp"] / (x["tp"] + x["fp"]) if x["tp"] + x["fp"] else None
        rc = x["tp"] / (x["tp"] + x["fn"]) if x["tp"] + x["fn"] else None
        return {**x, "precision": p, "recall": rc}

    agent = pr(m["agent"])
    agent["recall_first_pass_only"] = m["agent"]["tp_first_pass"] / n_blocking_defects if n_blocking_defects else None
    return {
        "n_defect_variants": n_defect_variants, "n_clean_variants": clean["n"],
        "n_blocking_defects": n_blocking_defects, "n_nonblocking_defects": n_nonblocking_defects,
        "blocking_detection": {"agent": agent, "axe": pr(m["axe"])},
        "breakpoint_step_localization": {"n_variants_with_blocking": loc["n"],
                                         "agent_accuracy": loc["agent"] / loc["n"] if loc["n"] else None,
                                         "axe_first_violating_step_accuracy": loc["axe"] / loc["n"] if loc["n"] else None},
        "journey_completion_defect_variants": {"before_repair": completed_before / n_defect_variants,
                                               "after_repair": completed_after / n_defect_variants,
                                               "handoff_to_human": handoff, "unresolved": unresolved},
        "clean_false_alarm": clean,
    }


def plot(metrics, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    bd = metrics["blocking_detection"]
    loc = metrics["breakpoint_step_localization"]
    jc = metrics["journey_completion_defect_variants"]
    labels = ["Recall lỗi blocking", "Precision lỗi blocking", "Định vị đúng bước gãy"]
    agent = [bd["agent"]["recall"], bd["agent"]["precision"], loc["agent_accuracy"]]
    axe = [bd["axe"]["recall"], bd["axe"]["precision"], loc["axe_first_violating_step_accuracy"]]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw={"width_ratios": [3, 2]})
    x = range(len(labels))
    b1 = a1.bar([i - 0.2 for i in x], agent, 0.4, label="Agent persona (bàn phím + cây a11y)", color="#2a6fdb")
    b2 = a1.bar([i + 0.2 for i in x], axe, 0.4, label="axe-core theo trang", color="#9aa4b2")
    for bars in (b1, b2):
        for b in bars:
            a1.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.01, f"{b.get_height():.2f}", ha="center", fontsize=9)
    a1.set_xticks(list(x), labels)
    a1.set_ylim(0, 1.12)
    a1.legend(fontsize=8, loc="upper right")
    a1.set_title(f"Phát hiện lỗi chặn hành trình (test, {metrics['n_defect_variants']} biến thể)", fontsize=10)
    vals = [jc["before_repair"], jc["after_repair"]]
    bars = a2.bar(["Trước vá", "Sau vá tự động"], vals, color=["#9aa4b2", "#2a6fdb"])
    for b in bars:
        a2.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.01, f"{b.get_height():.0%}", ha="center", fontsize=9)
    a2.set_ylim(0, 1.12)
    a2.set_title(f"Tỉ lệ hành trình hoàn thành (chuyển người: {jc['handoff_to_human']})", fontsize=10)
    for a in (a1, a2):
        a.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test"], required=True)
    args = ap.parse_args()
    out = ROOT / "out" / args.split
    (out / "pages").mkdir(parents=True, exist_ok=True)
    variants = build_variants(args.split, out)
    results = {}
    t0 = time.time()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        for v in variants:
            uri = pathlib.Path(v["path"]).as_uri()
            results[v["name"]] = {"agent": run_with_repair(page, uri), "axe": run_axe(page, v)}
        browser.close()
    metrics = score(variants, results)
    metrics["runtime_seconds"] = round(time.time() - t0, 1)
    (out / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    plot(metrics, out / "fig_bar.png")
    print(json.dumps(metrics, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
