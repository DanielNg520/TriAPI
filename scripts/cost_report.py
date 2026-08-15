"""Cost/token accounting for the 4-tier pipeline.

Two independent reports live here, both reading logs/cost_log.jsonl (every
tier logs its own token usage there -- tier1_escalate.py, tier2_escalate.py,
tier3_escalate.py, tier4_worker.py):

  report() / format_report()
      Per-task spend breakdown. Used by triapi.py after every dispatch item
      resolves -- unchanged behavior, existing callers keep working.

  run_summary() / format_run_report()
      Whole-run savings report: what the pipeline actually spent vs. what
      the same token volume would have cost if a single paid Claude model
      had done every item alone (no tiered fallback), plus, for Tier 4
      (local Ollama) specifically, its volume priced on a cloud tier next
      to the amortized cost of the GPU that makes local inference
      possible. Printed automatically at the end of `triapi dispatch`.

Claude pricing is hardcoded from Anthropic's published rates (see
CLAUDE_PRICING below) and DeepSeek's rates come from config/tiers.yaml --
this file only computes, it does not re-fetch prices. Re-verify
CLAUDE_PRICING before trusting this report months from now; API prices
change.

Usage:
    python3 -m scripts.cost_report --task-id <task_id>       # per-task
    python3 -m scripts.cost_report --run-id <run_id>          # whole-run
    python3 -m scripts.cost_report --run-id <run_id> --gpu-hours 2.5
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.config_loader import load_tiers

COST_LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "cost_log.jsonl"

# Anthropic list pricing, USD per million tokens. Verified against the
# claude-api skill's cached pricing table, 2026-08-11. Sonnet 5 intro
# pricing runs through 2026-08-31 -- after that date the $3/$15 row
# applies and this report will overstate the Claude-only baseline's cost
# advantage over the real pipeline unless updated.
CLAUDE_PRICING = {
    "claude-sonnet-5": {"input": 3.00, "output": 15.00, "intro_input": 2.00, "intro_output": 10.00},
    "claude-opus-5": {"input": 5.00, "output": 25.00},
}

# GPU-purchase comparison is inherently assumption-driven (hardware price,
# duty cycle, power draw, electricity rate all vary by buyer) -- these are
# CLI-overridable defaults, not asserted facts. Defaults describe a
# consumer 24GB card (e.g. RTX 4090) bought new, run at moderate load.
DEFAULT_GPU_PRICE_USD = 1600.0
DEFAULT_GPU_LIFETIME_YEARS = 3.0
DEFAULT_GPU_POWER_WATTS = 450.0
DEFAULT_ELECTRICITY_USD_PER_KWH = 0.15


# ---------------------------------------------------------------------------
# Minimal ANSI helpers -- no dependency, degrades to plain text when stdout
# isn't a terminal (piped to a file/log) so this never corrupts non-tty
# output with escape codes.
# ---------------------------------------------------------------------------
_USE_COLOR = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


def _bold(text: str) -> str:
    return _c("1", text)


def _green(text: str) -> str:
    return _c("1;32", text)


def _cyan(text: str) -> str:
    return _c("1;36", text)


def _dim(text: str) -> str:
    return _c("2", text)


def _yellow(text: str) -> str:
    return _c("33", text)


# ---------------------------------------------------------------------------
# Per-task report (existing behavior, unchanged) -- called by triapi.py
# after every dispatch item.
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Whole-run savings report.
# ---------------------------------------------------------------------------


def load_entries(run_id: str | None = None) -> list[dict]:
    if not COST_LOG_PATH.exists():
        return []
    entries = []
    with open(COST_LOG_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            if run_id and not entry.get("task_id", "").startswith(run_id):
                continue
            entries.append(entry)
    return entries


def _tier_tokens(entry: dict) -> tuple[int, int]:
    """Returns (input-ish tokens, output tokens) for one log entry,
    reading whichever field names that tier actually logs (each tier's
    escalate script uses its own upstream API's vocabulary -- see this
    file's docstring)."""
    tier = entry.get("tier")
    if tier in ("tier_1", "critique"):
        input_tok = (
            entry.get("input_tokens", 0)
            + entry.get("cache_creation_input_tokens", 0)
            + entry.get("cache_read_input_tokens", 0)
        )
        return input_tok, entry.get("output_tokens", 0)
    if tier == "tier_2":
        return entry.get("prompt_tokens", 0) + entry.get("cached_tokens", 0), entry.get("output_tokens", 0)
    if tier == "tier_3":
        return entry.get("cache_hit_tokens", 0) + entry.get("cache_miss_tokens", 0), entry.get("output_tokens", 0)
    if tier == "tier_4":
        return entry.get("prompt_eval_count", 0), entry.get("eval_count", 0)
    return 0, 0


def run_summary(entries: list[dict]) -> dict:
    per_tier = defaultdict(lambda: {"calls": 0, "input_tokens": 0, "output_tokens": 0, "actual_cost_usd": 0.0, "notional_cost_usd": 0.0})
    for e in entries:
        tier = e.get("tier", "unknown")
        in_tok, out_tok = _tier_tokens(e)
        row = per_tier[tier]
        row["calls"] += 1
        row["input_tokens"] += in_tok
        row["output_tokens"] += out_tok
        row["actual_cost_usd"] += e.get("cost_usd", 0.0) or 0.0
        row["notional_cost_usd"] += e.get("notional_cost_usd", 0.0) or 0.0
    return dict(per_tier)


def claude_baseline_cost(total_input: int, total_output: int, model: str, use_intro: bool) -> float:
    p = CLAUDE_PRICING[model]
    in_rate = p.get("intro_input", p["input"]) if use_intro else p["input"]
    out_rate = p.get("intro_output", p["output"]) if use_intro else p["output"]
    return total_input / 1_000_000 * in_rate + total_output / 1_000_000 * out_rate


def deepseek_flash_cost(total_input: int, total_output: int) -> float:
    """Prices Tier 4's volume as if it had run on Tier 3 (DeepSeek flash)
    instead of locally -- config/tiers.yaml's own verified pricing block,
    not a re-guess. output_per_mtok_usd is unverified there (None), so
    output tokens are priced at the cache-miss rate as a conservative
    stand-in, same convention tier3_escalate.py uses via its own
    cost_partial field."""
    tiers = load_tiers()
    pricing = tiers["tier_3_debugger"]["pricing"]["flash"]
    miss_rate = pricing.get("cache_miss_per_mtok_usd") or 0.0
    out_rate = pricing.get("output_per_mtok_usd") or miss_rate
    return total_input / 1_000_000 * miss_rate + total_output / 1_000_000 * out_rate


def gpu_amortized_cost(hours_used: float, gpu_price: float, lifetime_years: float, power_watts: float, elec_rate: float) -> dict:
    lifetime_hours = lifetime_years * 365 * 24
    hardware_share = gpu_price * (hours_used / lifetime_hours) if lifetime_hours else 0.0
    electricity = (power_watts / 1000) * hours_used * elec_rate
    return {"hardware_share_usd": hardware_share, "electricity_usd": electricity, "total_usd": hardware_share + electricity}


def format_run_report(entries: list[dict], args: argparse.Namespace) -> str:
    per_tier = run_summary(entries)
    lines = []
    title = "TriAPI cost & savings report" + (f"  ({args.run_id})" if args.run_id else "  (all runs)")
    bar = "═" * max(len(title) + 2, 60)
    lines.append(_cyan("╔" + bar + "╗"))
    lines.append(_cyan("║ ") + _bold(title) + " " * (len(bar) - len(title) - 1) + _cyan("║"))
    lines.append(_cyan("╚" + bar + "╝"))

    if not entries:
        lines.append("\nNo entries in logs/cost_log.jsonl yet -- nothing to report.")
        return "\n".join(lines)

    lines.append("")
    lines.append(_bold(f"{'TIER':<10} {'CALLS':>6} {'IN TOK':>10} {'OUT TOK':>10} {'ACTUAL $':>12} {'LIST-PRICE $':>14}"))
    lines.append(_dim("─" * 66))
    grand_calls = grand_in = grand_out = 0
    grand_actual = grand_notional = 0.0
    tier_labels = {
        "tier_1": "Tier 1 (Claude Code)",
        "tier_2": "Tier 2 (Gemini)",
        "tier_3": "Tier 3 (DeepSeek)",
        "tier_4": "Tier 4 (local Ollama)",
    }
    for tier in ["tier_1", "tier_2", "tier_3", "tier_4"]:
        row = per_tier.get(tier)
        if not row:
            continue
        lines.append(
            f"{tier:<10} {row['calls']:>6} {row['input_tokens']:>10,} {row['output_tokens']:>10,} "
            f"{row['actual_cost_usd']:>12.4f} {row['notional_cost_usd']:>14.4f}"
        )
        grand_calls += row["calls"]
        grand_in += row["input_tokens"]
        grand_out += row["output_tokens"]
        grand_actual += row["actual_cost_usd"]
        grand_notional += row["notional_cost_usd"]
    lines.append(_dim("─" * 66))
    lines.append(_bold(f"{'TOTAL':<10} {grand_calls:>6} {grand_in:>10,} {grand_out:>10,} {grand_actual:>12.4f} {grand_notional:>14.4f}"))
    lines.append(
        _dim(
            "\n(tier_1/tier_2 show $0 actual -- subscription/free-tier auth, not metered; "
            "'list-price $' is what that same usage would have cost metered. tier_3/tier_4 "
            "actual costs are real: tier_3 is billed API usage, tier_4 is $0 -- local hardware.)"
        )
    )

    # --- Headline number: what a single paid Claude model would have cost ---
    sonnet_std = claude_baseline_cost(grand_in, grand_out, "claude-sonnet-5", use_intro=False)
    opus_std = claude_baseline_cost(grand_in, grand_out, "claude-opus-5", use_intro=False)
    saved = sonnet_std - grand_actual
    pct = (saved / sonnet_std * 100) if sonnet_std else 0.0

    lines.append("")
    lines.append(_bold("If Claude alone had done every step (no tiering, API-metered):"))
    lines.append(f"  Sonnet 5:  {_bold('$' + f'{sonnet_std:.2f}')}    Opus 5:  {_bold('$' + f'{opus_std:.2f}')}")
    lines.append("")
    lines.append(_bold("What this run actually spent:") + "  " + _green(f"${grand_actual:.4f}"))
    lines.append(
        _green(_bold(f"  >> Estimated savings: ${saved:.2f}  ({pct:.1f}% cheaper than an all-Sonnet-5 baseline) <<"))
    )
    lines.append(
        _dim(
            "  Caveat: compares raw token volume, not equivalent turnaround time -- local/cheap "
            "tiers retry more than a single capable model would, so this is an upper bound on "
            "savings, not an exact substitution."
        )
    )

    # --- Tier 4 vs cloud vs GPU ownership ---
    t4 = per_tier.get("tier_4")
    lines.append("")
    lines.append(_bold("Tier 4 (local Ollama) vs. cloud API vs. GPU ownership:"))
    if not t4 or (t4["input_tokens"] == 0 and t4["output_tokens"] == 0):
        lines.append("  No Tier 4 token data logged yet.")
    else:
        cloud_equiv = deepseek_flash_cost(t4["input_tokens"], t4["output_tokens"])
        sonnet_equiv = claude_baseline_cost(t4["input_tokens"], t4["output_tokens"], "claude-sonnet-5", use_intro=False)
        lines.append(
            f"  {t4['input_tokens']:,} in + {t4['output_tokens']:,} out tokens across {t4['calls']} "
            f"call(s), at {_green('$0')} marginal cost (local hardware)."
        )
        lines.append(f"    Same volume on DeepSeek flash:   ${cloud_equiv:.4f}")
        lines.append(f"    Same volume on Claude Sonnet 5:  ${sonnet_equiv:.4f}")

        gpu = gpu_amortized_cost(
            args.gpu_hours, args.gpu_price, args.gpu_lifetime_years, args.gpu_power_watts, args.electricity_rate
        )
        lines.append(
            _yellow(
                f"    GPU ownership @ {args.gpu_hours:.1f}h used (assumption: ${args.gpu_price:.0f} card / "
                f"{args.gpu_lifetime_years:.1f}yr + {args.gpu_power_watts:.0f}W @ ${args.electricity_rate:.2f}/kWh): "
                f"${gpu['total_usd']:.4f}"
            )
        )
        if args.gpu_hours == 0:
            lines.append(
                _dim(
                    "    --gpu-hours defaults to 0 (no reliable usage-duration signal in this repo) -- "
                    "pass it explicitly for a real GPU-ownership figure."
                )
            )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-id", default=None, help="per-task report (original behavior)")
    parser.add_argument("--run-id", default=None, help="whole-run savings report, filtered by task_id prefix")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON instead of text (--task-id mode only)")
    parser.add_argument("--gpu-price", type=float, default=DEFAULT_GPU_PRICE_USD)
    parser.add_argument("--gpu-lifetime-years", type=float, default=DEFAULT_GPU_LIFETIME_YEARS)
    parser.add_argument("--gpu-power-watts", type=float, default=DEFAULT_GPU_POWER_WATTS)
    parser.add_argument("--electricity-rate", type=float, default=DEFAULT_ELECTRICITY_USD_PER_KWH, help="USD per kWh")
    parser.add_argument("--gpu-hours", type=float, default=0.0, help="wall-clock hours the GPU ran for this volume (no auto-detection)")
    args = parser.parse_args()

    if args.task_id:
        rep = report(args.task_id)
        print(json.dumps(rep) if args.json else format_report(rep))
        return

    entries = load_entries(args.run_id)
    print(format_run_report(entries, args))


if __name__ == "__main__":
    main()
