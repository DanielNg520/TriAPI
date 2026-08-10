"""Aggregates logs/cost_log.jsonl per task into a clear spend breakdown.

Distinguishes actual dollars spent (metered billing, e.g. DeepSeek) from
notional cost (what a call would have cost on metered billing, but was
actually covered by a subscription/free tier at $0 real cost) so the user
always knows exactly what a task cost them.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

COST_LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "cost_log.jsonl"


def report(task_id: str) -> dict:
    by_tier = defaultdict(lambda: {"calls": 0, "cost_usd": 0.0, "notional_cost_usd": 0.0, "partial": False})
    total_actual = 0.0

    if COST_LOG_PATH.exists():
        with open(COST_LOG_PATH) as f:
            for line in f:
                entry = json.loads(line)
                if entry.get("task_id") != task_id:
                    continue
                tier = entry["tier"]
                by_tier[tier]["calls"] += 1
                by_tier[tier]["cost_usd"] += entry.get("cost_usd", 0.0)
                by_tier[tier]["notional_cost_usd"] += entry.get("notional_cost_usd", 0.0)
                if entry.get("cost_partial"):
                    by_tier[tier]["partial"] = True
                total_actual += entry.get("cost_usd", 0.0)

    return {"task_id": task_id, "by_tier": dict(by_tier), "total_actual_usd": round(total_actual, 8)}


def format_report(rep: dict) -> str:
    lines = [f"Cost report for task '{rep['task_id']}':"]
    if not rep["by_tier"]:
        lines.append("  No paid-tier calls recorded (resolved locally, or no data yet).")
    for tier in sorted(rep["by_tier"]):
        d = rep["by_tier"][tier]
        line = f"  {tier}: {d['calls']} call(s), ${d['cost_usd']:.6f} actual"
        if d["notional_cost_usd"]:
            line += f" (${d['notional_cost_usd']:.4f} notional, subscription-covered)"
        if d["partial"]:
            line += " [partial: some pricing in tiers.yaml is unverified]"
        lines.append(line)
    lines.append(f"Total actual spend: ${rep['total_actual_usd']:.6f}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON instead of text")
    args = parser.parse_args()

    rep = report(args.task_id)
    print(json.dumps(rep) if args.json else format_report(rep))


if __name__ == "__main__":
    main()
