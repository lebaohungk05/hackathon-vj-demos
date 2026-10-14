import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

OUT = Path(__file__).parent / "out"
AGENT = "#2a78d6"
BASELINE = "#eb6834"
ORACLE = "#8a8984"
RAIN = "#1baf7a"
INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e4e3df"
SURFACE = "#fcfcfb"

ACTION_STYLE = {
    "irrigate": ("^", AGENT, "Được bơm (agent)"),
    "hold_rain": ("D", RAIN, "Giữ lệnh bơm do mưa"),
    "remeasure": ("o", "#4a3aa7", "Yêu cầu đo lại"),
    "flag_sensor": ("X", "#e34948", "Gắn cờ cảm biến"),
    "flag_photo": ("P", "#eda100", "Gắn cờ ảnh đọc sai"),
    "escalate": ("s", "#e87ba4", "Báo HTX: thiếu nhật ký"),
}

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.edgecolor": GRID,
    "axes.labelcolor": MUTED,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.facecolor": SURFACE,
    "figure.facecolor": SURFACE,
    "axes.spines.top": False,
    "axes.spines.right": False,
})


def pick_cluster(labels, seed):
    faults = labels[(labels.seed == seed) & labels.fault.isin(["a_sensor", "c_photo_misread", "d_pump_schedule", "b_missing_logs"])]
    counts = faults.groupby("cluster")["fault"].nunique()
    return int(counts.idxmax())


def cluster_trace(split="test"):
    folder = OUT / split
    gt = pd.read_csv(folder / "ground_truth.csv", parse_dates=["date"])
    actions = pd.read_csv(folder / "actions.csv")
    labels = pd.read_csv(folder / "labels.csv")
    seed = int(gt.seed.min())
    cluster = pick_cluster(labels, seed)
    gt = gt[(gt.seed == seed) & (gt.cluster == cluster)]
    agent = gt[gt.policy == "agent"]
    baseline = gt[gt.policy == "baseline"]
    acts = actions[(actions.seed == seed) & (actions.policy == "agent") & actions.action.isin(ACTION_STYLE)]
    acts = acts.drop_duplicates(["pid", "day", "action"])
    day_to_date = dict(zip(agent.day, agent.date))
    pids = sorted(agent.pid.unique())

    fig, axes = plt.subplots(len(pids) + 1, 1, figsize=(11, 13), sharex=True, gridspec_kw={"height_ratios": [1.1] + [1] * len(pids)})
    rain = agent.drop_duplicates("day")
    axes[0].bar(rain.date, rain.rain_mm, color=RAIN, width=0.8)
    axes[0].set_ylabel("Mưa (mm/ngày)")
    site = "An Giang" if cluster < 3 else "Cần Thơ"
    axes[0].set_title(f"Cụm {cluster + 1} ({site}), 6 thửa chung một trạm bơm: mực nước thật trong mô phỏng\nMưa: dữ liệu thật Open-Meteo, Đông Xuân 2025-26. Mực nước, lỗi và hành động: mô phỏng (seed kiểm tra {seed})", loc="left", color=INK, fontsize=10)
    axes[0].grid(axis="y", color=GRID, linewidth=0.6)

    for ax, pid in zip(axes[1:], pids):
        a = agent[agent.pid == pid]
        b = baseline[baseline.pid == pid]
        heading = a[a.stage == "heading"]
        ax.axvspan(heading.date.min(), heading.date.max(), color="#f3efe0", zorder=0)
        ax.axhline(-15, color="#e34948", linestyle="--", linewidth=1)
        ax.axhline(0, color=GRID, linewidth=0.8)
        ax.plot(b.date, b.true_level_cm, color=BASELINE, linewidth=1.4, alpha=0.9)
        ax.plot(a.date, a.true_level_cm, color=AGENT, linewidth=2)
        level = dict(zip(a.day, a.true_level_cm))
        for action, (marker, color, _) in ACTION_STYLE.items():
            sel = acts[(acts.pid == pid) & (acts.action == action)]
            if action == "irrigate":
                sel = a[a.irrigation_mm > 0]
                ys = [-27] * len(sel)
            else:
                ys = [level.get(d, np.nan) for d in sel.day]
            ax.scatter([day_to_date[d] for d in sel.day if d in day_to_date], [y for d, y in zip(sel.day, ys) if d in day_to_date], marker=marker, s=34, color=color, edgecolor=SURFACE, linewidth=0.8, zorder=5)
        plot_labels = labels[(labels.seed == seed) & (labels.pid == pid) & labels.fault.isin(["a_sensor", "c_photo_misread", "b_missing_logs"])]
        for n, (_, lab) in enumerate(plot_labels.sort_values("day").iterrows()):
            if lab.day in day_to_date:
                ax.annotate({"a_sensor": "lỗi cảm biến", "c_photo_misread": "ảnh sai", "b_missing_logs": "mất nhật ký"}[lab.fault], (day_to_date[lab.day], 12 - 4 * (n % 3)), fontsize=7, color=MUTED, ha="left")
        info = labels[(labels.seed == seed) & (labels.pid == pid) & (labels.fault == "e_proxy_logging")]
        tag = " · HTX ghi hộ" if len(info) else ""
        ax.set_ylim(-30, 15)
        ax.set_ylabel(f"Thửa {int(a.iloc[0]['plot']) + 1}{tag}\n(cm)", fontsize=8)
        ax.grid(axis="y", color=GRID, linewidth=0.6)
    changes = labels[(labels.seed == seed) & (labels.cluster == cluster) & (labels.fault == "d_pump_schedule")].sort_values("day")
    for n, (_, ch) in enumerate(changes.iterrows()):
        if ch.day in day_to_date:
            for ax in axes[1:]:
                ax.axvline(day_to_date[ch.day], color=MUTED, linestyle=":", linewidth=1)
            axes[0].annotate("lịch bơm đổi (báo trước)" if "moved" in ch.detail else "bơm hỏng, không báo", (day_to_date[ch.day], 0.92 - 0.12 * n), xycoords=("data", "axes fraction"), fontsize=7, color=MUTED)
            axes[0].axvline(day_to_date[ch.day], color=MUTED, linestyle=":", linewidth=1)

    handles = [
        plt.Line2D([], [], color=AGENT, linewidth=2, label="Mực nước thật, có agent"),
        plt.Line2D([], [], color=BASELINE, linewidth=1.4, label="Mực nước thật, lịch cố định"),
        plt.Line2D([], [], color="#e34948", linestyle="--", label="Ngưỡng AWD an toàn −15 cm"),
        plt.Rectangle((0, 0), 1, 1, color="#f3efe0", label="Trổ bông (không để khô)"),
    ] + [plt.Line2D([], [], marker=m, color=c, linestyle="", markersize=6, label=l) for m, c, l in ACTION_STYLE.values()]
    fig.legend(handles=handles, loc="lower center", ncol=5, frameon=False, fontsize=8)
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    path = folder / "fig_cluster_trace.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def comparison_bars(split="test"):
    folder = OUT / split
    summary = json.loads((folder / "results.json").read_text(encoding="utf-8"))["summary"]
    panels = [
        ("awd_violation_plot_days", "Ngày-thửa khô quá ngưỡng AWD\n(dưới −15 cm quá 2 ngày)", "thấp hơn là tốt"),
        ("heading_dry_plot_days", "Ngày-thửa khô lúc trổ bông\n(dưới −5 cm)", "thấp hơn là tốt"),
        ("evidence_completeness_pct", "Độ đầy đủ bằng chứng (%)\n(khối 3 ngày có số đo đúng ±3 cm)", "cao hơn là tốt"),
        ("pump_days_used", "Số ngày trạm bơm chạy\n(5 cụm, cả vụ)", "chi phí vận hành"),
    ]
    policies = [("baseline", "Lịch cố định", BASELINE), ("agent", "Agent", AGENT), ("oracle", "Biết mực nước thật\n(mốc tham chiếu)", ORACLE)]
    fig, axes = plt.subplots(1, len(panels), figsize=(12, 3.8))
    for ax, (key, title, note) in zip(axes, panels):
        for i, (name, label, color) in enumerate(policies):
            s = summary[name][key]
            ax.bar(i, s["mean"], color=color, width=0.62)
            ax.errorbar(i, s["mean"], yerr=[[s["mean"] - s["min"]], [s["max"] - s["mean"]]], color=INK, capsize=3, linewidth=1)
            ax.annotate(f"{s['mean']:.0f}" if s["mean"] >= 10 else f"{s['mean']:.1f}", (i, s["max"]), xytext=(0, 4), textcoords="offset points", ha="center", fontsize=8, color=INK)
        ax.set_xticks(range(len(policies)), [p[1] for p in policies], fontsize=7.5)
        ax.set_title(title, fontsize=9, color=INK, loc="left")
        ax.text(0, -0.28, note, transform=ax.transAxes, fontsize=7.5, color=MUTED)
        ax.grid(axis="y", color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
    seeds = json.loads((folder / "results.json").read_text(encoding="utf-8"))["seeds"]
    fig.suptitle(f"Mô phỏng 30 thửa × {len(seeds)} seed kiểm tra (không dùng để chỉnh agent). Cột = trung bình, vạch = min–max", x=0.01, ha="left", fontsize=10, color=INK)
    fig.tight_layout()
    path = folder / "fig_agent_vs_baseline.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


if __name__ == "__main__":
    split = sys.argv[1] if len(sys.argv) > 1 else "test"
    print(cluster_trace(split))
    print(comparison_bars(split))
