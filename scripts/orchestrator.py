"""Ties Tier 4 -> Tier 3 -> Tier 1 -> Tier 2 -> human handoff together.

Tier 4 (Ollama) drafts AND rebuilds each attempt. Once it escalates, Tiers
3/1/2 only patch the file and hand back to a plain rebuild (scripts.tier4_worker.run_build)
-- they must NOT trigger another Ollama draft, which would overwrite their fix.

State is file-backed (logs/state/<task_id>.json) so this can be re-entered
across process invocations, matching how Tier 4 is expected to run.
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.budget_guard import check_tier1_ok, check_tier2_ok
from scripts.config_loader import load_tiers
from scripts.cost_report import format_report, report
from scripts.state import clear_state, read_state, record_failure
from scripts.tier1_escalate import escalate as tier1_escalate
from scripts.tier2_escalate import escalate as tier2_escalate
from scripts.tier3_escalate import escalate as tier3_escalate
from scripts.tier4_worker import run as tier4_run
from scripts.tier4_worker import run_build
from scripts.tri_logging import get_logger

log = get_logger("orchestrator")

ESCALATIONS_LOG = Path(__file__).resolve().parent.parent / "logs" / "escalations.jsonl"
ESCALATIONS_DIR = Path(__file__).resolve().parent.parent / "logs"


def _rebuild_after_patch(task_id: str, build_cmd: str, workdir: str) -> bool:
    """Rebuilds without re-drafting; records failure/clears state accordingly."""
    ok, output = run_build(build_cmd, workdir)
    if ok:
        clear_state(task_id)
    else:
        record_failure(task_id, output)
    return ok


def human_handoff(task_id: str, reason: str, detail: str = "") -> None:
    """Writes a human-handoff record. Public and reusable by any dispatcher
    (not just the file-fix chain below) that needs to report an unresolved
    item -- e.g. dispatcher.py's git steps use this too."""
    entry = {"timestamp": time.time(), "task_id": task_id, "reason": reason}
    ESCALATIONS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(ESCALATIONS_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")

    summary_path = ESCALATIONS_DIR / f"escalation_{task_id}.md"
    summary_path.write_text(
        f"# Escalation: {task_id}\n\n"
        f"**Reason:** {reason}\n\n"
        f"{detail}\n\n"
        f"This task could not be resolved automatically. Review manually -- e.g. "
        f"in Antigravity or a normal editor.\n"
    )
    print(f"[HUMAN HANDOFF] Task '{task_id}' needs manual review: {reason}")
    print(f"[HUMAN HANDOFF] See {summary_path}")
    log.warning("[%s] Human handoff: %s", task_id, reason)


def run_task(task_id: str, description: str, target: str, workdir: str = ".", build_cmd: str | None = None, tier4_model: str | None = None) -> dict:
    config = load_tiers()
    build_cmd = build_cmd or " && ".join(config["tier_4_worker"]["build_commands"])

    # tier4_run resolves target against workdir internally; tiers 1-3 don't
    # take a workdir argument, so resolve once here and pass the full path.
    target_arg = Path(target)
    resolved_target = str(target_arg if target_arg.is_absolute() else Path(workdir) / target_arg)

    resolved_by = None
    log.info("[%s] run_task starting: target=%s workdir=%s", task_id, target, workdir)

    # Tier 4: draft + build loop, until success or escalate.
    while True:
        result = tier4_run(task_id, description, target, workdir, build_cmd, tier4_model)
        log.info("[%s] Tier 4 attempt: %s (consecutive_failures=%s)", task_id, result["status"], result.get("consecutive_failures"))
        if result["status"] == "success":
            resolved_by = "tier_4"
            break
        if result["status"] == "escalate":
            break
        # status == "build_failed": loop again (another Tier 4 attempt)

    if resolved_by is None:
        # Tier 3: DeepSeek
        tier3_escalate(task_id, resolved_target)
        if _rebuild_after_patch(task_id, build_cmd, workdir):
            resolved_by = "tier_3"

    if resolved_by is None:
        # Tier 1: Claude Code CLI (budget-guarded)
        guard1 = check_tier1_ok()
        if guard1["ok"]:
            tier1_escalate(task_id, resolved_target)
            if _rebuild_after_patch(task_id, build_cmd, workdir):
                resolved_by = "tier_1"
        else:
            print(f"[BUDGET GUARD] Tier 1 skipped: {guard1['reason']}")

    if resolved_by is None:
        # Tier 2: Gemini API (budget-guarded)
        guard2 = check_tier2_ok()
        if guard2["ok"]:
            tier2_escalate(task_id, resolved_target)
            if _rebuild_after_patch(task_id, build_cmd, workdir):
                resolved_by = "tier_2"
        else:
            print(f"[BUDGET GUARD] Tier 2 skipped: {guard2['reason']}")

    if resolved_by is None:
        handoff_state = read_state(task_id)
        detail = (
            f"**Consecutive failures recorded:** {handoff_state.get('consecutive_failures')}\n\n"
            f"**Last build error:**\n```\n{handoff_state.get('last_stderr', '')}\n```"
        )
        human_handoff(task_id, "unresolved after Tier 4 -> Tier 3 -> Tier 1 -> Tier 2", detail)
        status = "human_handoff"
    else:
        status = "success"

    log.info("[%s] run_task finished: status=%s resolved_by=%s", task_id, status, resolved_by)
    cost_rep = report(task_id)
    return {"status": status, "resolved_by": resolved_by, "cost_report": cost_rep}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--workdir", default=".")
    parser.add_argument("--build-cmd", default=None)
    parser.add_argument("--tier4-model", default=None, help="overrides config default Tier 4 draft model")
    args = parser.parse_args()

    result = run_task(args.task_id, args.description, args.target, args.workdir, args.build_cmd, args.tier4_model)
    print(json.dumps({"status": result["status"], "resolved_by": result["resolved_by"]}))
    print()
    print(format_report(result["cost_report"]))


if __name__ == "__main__":
    main()
