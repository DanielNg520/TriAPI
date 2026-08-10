#!/usr/bin/env python3
"""TriAPI natural-language entry point.

Two-step by design: `plan` is an interactive conversation with Claude
(Tier 1) to nail down exactly what should be built before anything is
built -- getting the plan wrong and letting execution run with it is what
actually costs time and money, so review happens here, up front, for free
(subscription quota). `dispatch` then takes an *approved* plan, has Gemini
(Tier 2) break it into a phase/checklist structure, and works through it
one item at a time via the existing repair pipeline (orchestrator.py).

`dispatch` is the part that can run unattended and detached (--background)
-- planning always needs a human in the loop, so it's foreground-only.
This split matters for low-friction remote use over SSH (e.g. Tailscale):
plan interactively while connected, then let a long dispatch run survive
a dropped connection.

Usage:
    triapi plan "there is a plan.md in this project, follow it strictly"
    triapi plan "..." --project-dir ~/projects/foo
    triapi dispatch <run_id>
    triapi dispatch <run_id> --background
    triapi status <run_id>
    triapi list
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import dispatcher, planner, resource_guard
from scripts.config_loader import load_resource_guard_services
from scripts.cost_report import report as cost_report
from scripts.tri_logging import get_logger

log = get_logger("cli")

RUNS_DIR = Path(__file__).resolve().parent.parent / "logs" / "runs"

APPROVE_WORDS = {"approve", "approved", "looks good", "lgtm", "yes", "go", "proceed"}
CANCEL_WORDS = {"cancel", "abort", "stop", "no"}


def cmd_plan(prompt: str, project_dir: str) -> None:
    state = dispatcher.new_run(prompt, project_dir)
    log.info("[%s] triapi plan started: project_dir=%s", state["run_id"], project_dir)
    print(f"Run ID: {state['run_id']}\n")

    session_id = None
    message = prompt
    total_notional = 0.0

    while True:
        turn = planner.plan_turn(message, project_dir, session_id)
        if turn["status"] != "ok":
            print(f"Planning failed: {turn.get('reason')}")
            state["status"] = "failed"
            dispatcher.save_run(state)
            return

        session_id = turn["session_id"]
        total_notional += turn.get("notional_cost_usd", 0.0)
        print(turn["text"])
        print()

        try:
            reply = input("Your feedback, or 'approve' to proceed, or 'cancel' to abort: ").strip()
        except EOFError:
            print(
                "\nNo input available -- 'triapi plan' needs an interactive terminal "
                "(it can't run under --background). Aborting."
            )
            state["status"] = "failed"
            dispatcher.save_run(state)
            return

        if reply.lower() in APPROVE_WORDS:
            state["plan_text"] = turn["text"]
            state["status"] = "planned"
            dispatcher.save_run(state)
            log.info("[%s] Plan approved (total notional cost $%.4f)", state["run_id"], total_notional)
            print(f"\nPlan approved. Planning cost (notional, subscription-covered): ${total_notional:.4f}")
            print(f"Run it: triapi dispatch {state['run_id']}")
            return

        if reply.lower() in CANCEL_WORDS:
            state["status"] = "cancelled"
            dispatcher.save_run(state)
            log.info("[%s] Plan cancelled by user", state["run_id"])
            print("Cancelled.")
            return

        message = reply
        print()


def _breakdown_and_dispatch(state: dict) -> None:
    print("Breaking down plan into a checklist, one phase at a time (Tier 2 / Gemini)...")
    breakdown_result = dispatcher.breakdown_plan(state)  # mutates and saves state incrementally
    if breakdown_result["status"] != "ok":
        print(f"Breakdown failed: {breakdown_result.get('reason')}")
        state["status"] = "failed"
        dispatcher.save_run(state)
        return

    total_items = sum(len(p["items"]) for p in state["breakdown"]["phases"])
    print(
        f"\n{len(state['breakdown']['phases'])} phase(s), {total_items} step(s) total. "
        f"Dispatching one at a time...\n"
    )

    state = dispatcher.dispatch(state)

    print(f"\nRun {state['run_id']} finished with status: {state['status']}")
    total_actual = 0.0
    for r in state["results"]:
        rep = cost_report(r["task_id"])
        total_actual += rep["total_actual_usd"]
        print(f"  [{r['phase']}] {r['item']}: {r['status']} ({r['resolved_by']})")
    print(f"\nTotal actual spend across this run: ${total_actual:.6f}")

    if state["status"] == "stopped_on_failure":
        last = state["results"][-1]
        print(
            f"\nStopped: '{last['item']}' could not be resolved automatically. "
            f"See logs/escalation_{last['task_id']}.md for details. Fix it manually, "
            f"then resume with: triapi dispatch {state['run_id']}"
        )


def cmd_dispatch(run_id: str, background: bool) -> None:
    state = dispatcher.load_run(run_id)
    if state["status"] not in ("planned", "dispatching", "stopped_on_failure"):
        log.warning("[%s] Dispatch refused: status=%s", run_id, state["status"])
        print(f"Run {run_id} is not ready to dispatch (status: {state['status']}).")
        if state["status"] in ("planning", None):
            print(f"Finish planning first: triapi plan is still in progress for this run.")
        return
    if state["plan_text"] is None:
        print(f"Run {run_id} has no approved plan yet.")
        return

    if background:
        log.info("[%s] Spawning detached dispatch process", run_id)
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        log_path = RUNS_DIR / f"{run_id}.log"
        script_path = Path(__file__).resolve()
        with open(log_path, "w") as log_file:
            subprocess.Popen(
                [sys.executable, str(script_path), "dispatch", run_id],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
                cwd=str(Path(__file__).resolve().parent.parent),
            )
        print(f"Dispatching in background. Run ID: {run_id}")
        print(f"Check progress:  triapi status {run_id}")
        print(f"Raw log:         tail -f {log_path}")
        return

    # Pause resource-competing services (config/resource_guard.yaml) for the
    # duration of the run, resume them no matter how it ends -- success,
    # a stopped-on-failure item, or an uncaught exception. Covers both the
    # foreground path and the --background path, since the detached child
    # re-execs `dispatch <run_id>` without --background and lands here too.
    paused = resource_guard.pause_services(load_resource_guard_services())
    try:
        _breakdown_and_dispatch(state)
    finally:
        resource_guard.resume_services(paused)


def cmd_status(run_id: str) -> None:
    state = dispatcher.load_run(run_id)
    print(f"Run {run_id}: {state['status']}")
    print(f"Prompt: {state['prompt']}")
    print(f"Project dir: {state['project_dir']}")
    if state["breakdown"]:
        total_items = sum(len(p["items"]) for p in state["breakdown"]["phases"])
        print(f"Progress: {len(state['results'])}/{total_items} step(s) completed")
    for r in state["results"]:
        print(f"  [{r['phase']}] {r['item']}: {r['status']} ({r['resolved_by']})")


def cmd_list() -> None:
    runs = dispatcher.list_runs()
    if not runs:
        print("No runs yet.")
        return
    for r in runs:
        started = time.strftime("%Y-%m-%d %H:%M", time.localtime(r["started_at"]))
        prompt_preview = r["prompt"][:60] + ("..." if len(r["prompt"]) > 60 else "")
        print(f"{r['run_id']}  [{r['status']:>18}]  {started}  {prompt_preview}")


def main():
    parser = argparse.ArgumentParser(description="TriAPI natural-language pipeline entry point")
    sub = parser.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser("plan", help="interactively define and approve an execution plan")
    p_plan.add_argument("prompt")
    p_plan.add_argument("--project-dir", default=".")

    p_dispatch = sub.add_parser("dispatch", help="execute an approved plan")
    p_dispatch.add_argument("run_id")
    p_dispatch.add_argument("--background", action="store_true", help="run detached, safe against SSH disconnects")

    p_status = sub.add_parser("status", help="show progress of a run")
    p_status.add_argument("run_id")

    sub.add_parser("list", help="list all runs")

    args = parser.parse_args()

    if args.command == "plan":
        cmd_plan(args.prompt, args.project_dir)
    elif args.command == "dispatch":
        cmd_dispatch(args.run_id, args.background)
    elif args.command == "status":
        cmd_status(args.run_id)
    elif args.command == "list":
        cmd_list()


if __name__ == "__main__":
    main()
