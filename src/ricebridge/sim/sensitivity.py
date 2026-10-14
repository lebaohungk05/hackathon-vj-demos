import json

from experiment import OUT, TEST_SEEDS, run_one, summarize
from policies import AgentPolicy, BaselinePolicy, OraclePolicy

CAPACITIES = (3, 4, 6)
KEYS = ("awd_violation_plot_days", "heading_dry_plot_days", "awd_drying_plot_days", "pump_days_used")


def main():
    table = {}
    for capacity in CAPACITIES:
        table[capacity] = {}
        for cls in (AgentPolicy, BaselinePolicy, OraclePolicy):
            rows = [{k: run_one(seed, cls, pump_capacity=capacity)[3][k] for k in KEYS} for seed in TEST_SEEDS]
            table[capacity][cls.name] = summarize(rows)
    (OUT / "test" / "sensitivity_pump_capacity.json").write_text(json.dumps(table, indent=2), encoding="utf-8")
    return table


if __name__ == "__main__":
    for cap, res in main().items():
        print(cap, {p: {k: v["mean"] for k, v in r.items()} for p, r in res.items()})
