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
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import agents_md_gate, budget_guard, dispatcher, git_ops, jules_client, llm_client, planner, resource_guard, self_fix
from scripts.config_loader import load_resource_guard_services, load_tiers, load_unload_ollama_models_flag
from scripts.cost_report import (
    DEFAULT_ELECTRICITY_USD_PER_KWH,
    DEFAULT_GPU_LIFETIME_YEARS,
    DEFAULT_GPU_POWER_WATTS,
    DEFAULT_GPU_PRICE_USD,
    format_run_report,
    load_entries,
)
from scripts.cost_report import report as cost_report
from scripts.tri_logging import get_logger

log = get_logger("cli")

RUNS_DIR = Path(__file__).resolve().parent.parent / "logs" / "runs"

APPROVE_WORDS = {"approve", "approved", "looks good", "lgtm", "yes", "go", "proceed"}
CANCEL_WORDS = {"cancel", "abort", "stop", "no"}


def cmd_plan(prompt: str, project_dir: str, refactor: bool = False) -> None:
    if not refactor:
        incomplete = agents_md_gate.find_incomplete_plan(project_dir)
        if incomplete:
            print(
                f"Refusing to plan: this repo's AGENTS.md already has an appended "
                f"TriAPI plan (run {incomplete['run_id']}) with {incomplete['unchecked_count']} "
                f"unchecked step(s) left. Finish it first -- resume with "
                f"`triapi dispatch {incomplete['run_id']}`, or check `triapi status "
                f"{incomplete['run_id']}` if it's stuck on a human_handoff -- or pass "
                f"`triapi plan ... --refactor` if this goal is a deliberate refactor/pivot "
                f"that supersedes it."
            )
            log.info(
                "[plan] Refused: incomplete plan run_id=%s unchecked=%d project_dir=%s",
                incomplete["run_id"], incomplete["unchecked_count"], project_dir,
            )
            return

    state = dispatcher.new_run(prompt, project_dir)
    log.info("[%s] triapi plan started: project_dir=%s", state["run_id"], project_dir)
    print(f"Run ID: {state['run_id']}\n")

    session_id = None
    message = prompt
    total_notional = 0.0
    # Accumulated (user, assistant) turn pairs, oldest first -- passed to
    # planner.plan_turn() so non-'cli' providers (which have no server-side
    # session/--resume, unlike the 'cli' provider) can still see the full
    # conversation on turn 2+ instead of just the latest reply. See
    # planner.py's plan_turn() docstring for how each provider uses this.
    history: list[dict[str, str]] = []

    while True:
        try:
            turn = planner.plan_turn(message, project_dir, session_id, history=history)
        except Exception as exc:
            log.warning("Planning failed: %s", exc)
            print("Planning failed: could not reach the LLM backend.")
            state["status"] = "failed"
            dispatcher.save_run(state)
            raise SystemExit(1)
        if turn["status"] != "ok":
            log.warning("Planning failed: %s", turn.get("reason"))
            print("Planning failed: could not complete planning.")
            state["status"] = "failed"
            dispatcher.save_run(state)
            raise SystemExit(1)

        session_id = turn["session_id"]
        total_notional += turn.get("notional_cost_usd", 0.0)
        print(turn["text"])
        print()

        concerns = planner.detect_degenerate_plan(turn["text"])
        if concerns:
            print("WARNING: this response looks suspicious:")
            for c in concerns:
                print(f"  - {c}")
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

        if reply.lower() in APPROVE_WORDS and concerns:
            # Never let a single (e.g. blind piped) 'approve' auto-approve
            # a turn flagged above -- require an explicit second
            # confirmation. A blind pipe supplying only one line hits
            # EOFError here and aborts instead of silently approving
            # fabricated/truncated/degenerate content (2026-08-28).
            try:
                confirm = input(
                    "This plan was flagged as suspicious (see warning above). "
                    "Type 'approve' once more to confirm you've read it and still "
                    "want to proceed, or give feedback/'cancel': "
                ).strip()
            except EOFError:
                print(
                    "\nNo input available to confirm a flagged plan -- refusing to "
                    "auto-approve suspicious content. Aborting."
                )
                state["status"] = "failed"
                dispatcher.save_run(state)
                return
            if confirm.lower() in CANCEL_WORDS:
                state["status"] = "cancelled"
                dispatcher.save_run(state)
                log.info("[%s] Plan cancelled by user (after suspicious-content warning)", state["run_id"])
                print("Cancelled.")
                return
            if confirm.lower() not in APPROVE_WORDS:
                history.append({"user": message, "assistant": turn["text"]})
                message = confirm
                print()
                continue
            log.warning("[%s] Plan approved despite flagged concerns: %s", state["run_id"], concerns)
            reply = confirm

        if reply.lower() in APPROVE_WORDS:
            state["plan_text"] = turn["text"]
            state["status"] = "planned"
            dispatcher.save_run(state)
            agents_md_gate.append_plan(
                project_dir, state["run_id"], turn["text"],
                datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            )
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

        history.append({"user": message, "assistant": turn["text"]})
        message = reply
        print()


def _breakdown_and_dispatch(state: dict) -> None:
    print("Breaking down plan into a checklist, one phase at a time (Tier 2 / Gemini)...")
    try:
        breakdown_result = dispatcher.breakdown_plan(state)  # mutates and saves state incrementally
    except Exception as exc:
        log.warning("Breakdown failed: %s", exc)
        print("Breakdown failed: could not reach the LLM backend.")
        state["status"] = "stopped_on_failure"
        dispatcher.save_run(state)
        raise
    if breakdown_result["status"] != "ok":
        log.warning("Breakdown failed: %s", breakdown_result.get("reason"))
        print("Breakdown failed: could not complete the breakdown.")
        # breakdown_plan() saves completed phases incrementally and resumes
        # past them on re-entry, so a breakdown failure is not terminal --
        # "failed" previously blocked `triapi dispatch <run_id>` from ever
        # resuming (cmd_dispatch only accepts planned/dispatching/
        # stopped_on_failure), forcing a hand-patch of the stored run JSON
        # to retry a condition (e.g. a daily Gemini quota) that clears on
        # its own. "stopped_on_failure" is already in that accepted set.
        state["status"] = "stopped_on_failure"
        dispatcher.save_run(state)
        raise SystemExit(1)

    total_items = sum(len(p["items"]) for p in state["breakdown"]["phases"])
    print(
        f"\n{len(state['breakdown']['phases'])} phase(s), {total_items} step(s) total. "
        f"Dispatching one at a time...\n"
    )

    try:
        state = dispatcher.dispatch(state)
    except Exception as exc:
        log.warning("Dispatching failed: %s", exc)
        print("Dispatching failed: could not reach the LLM backend.")
        state["status"] = "stopped_on_failure"
        dispatcher.save_run(state)
        raise

    print(f"\nRun {state['run_id']} finished with status: {state['status']}")
    total_actual = 0.0
    for r in state["results"]:
        rep = cost_report(r["task_id"])
        total_actual += rep["total_actual_usd"]
        print(f"  [{r['phase']}] {r['item']}: {r['status']} ({r['resolved_by']})")
    print(f"\nTotal actual spend across this run: ${total_actual:.6f}")

    print()
    print(format_run_report(
        load_entries(state["run_id"]),
        argparse.Namespace(
            run_id=state["run_id"],
            gpu_price=DEFAULT_GPU_PRICE_USD,
            gpu_lifetime_years=DEFAULT_GPU_LIFETIME_YEARS,
            gpu_power_watts=DEFAULT_GPU_POWER_WATTS,
            electricity_rate=DEFAULT_ELECTRICITY_USD_PER_KWH,
            gpu_hours=0.0,
        ),
    ))

    if state["status"] == "completed":
        agents_md_gate.mark_plan_complete(state["project_dir"], state["run_id"], sum(len(p["items"]) for p in state["breakdown"]["phases"]))
        jules_check = budget_guard.check_jules_ok()
        if not jules_check["ok"]:
            print(f"\nSkipping Jules advisory test: {jules_check['reason']}")
            log.info("[%s] Skipping Jules advisory test: %s", state["run_id"], jules_check["reason"])
        else:
            push_result = git_ops.push(state["project_dir"], f"TriAPI run {state['run_id']}: {state['prompt'][:72]}")
            if not push_result["ok"]:
                print(f"\nJules advisory test skipped: push failed: {push_result['output'][:500]}")
                log.warning("[%s] Jules advisory test skipped: push failed: %s", state["run_id"], push_result["output"][:500])
            else:
                budget_guard.record_jules_call()
                jules_config = load_tiers().get("jules_tester", {})
                owner_repo = git_ops.get_github_owner_repo(state["project_dir"])
                if owner_repo:
                    source = f"sources/github/{owner_repo[0]}/{owner_repo[1]}"
                else:
                    # Non-github.com origin (or lookup failed): fall back to
                    # the configured default rather than guessing further.
                    source = jules_config.get("source", "")
                jules_result = jules_client.run_jules_test(
                    prompt=(
                        "This branch was just produced by an automated TriAPI dispatch run "
                        f"(run {state['run_id']}, original task: {state['prompt']}). "
                        "Read AGENTS.md if present for the documented test command, then run "
                        "this repository's existing test suite/build commands and reply with "
                        "a clear pass/fail summary, including failure details if any tests "
                        "failed. Do NOT modify, commit, or push any files, and do NOT open a "
                        "pull request -- this is a read-only verification pass only."
                    ),
                    source=source,
                    title=f"TriAPI advisory test: {state['run_id']}",
                    starting_branch=push_result.get("branch", "main"),
                    poll_interval=jules_config.get("poll_interval_s", jules_client.DEFAULT_POLL_INTERVAL_SECONDS),
                    timeout=jules_config.get("poll_timeout_s", jules_client.DEFAULT_POLL_TIMEOUT_SECONDS),
                )
                status = jules_result.get("status")
                if status == "completed":
                    print(f"\nJules advisory test completed: {jules_result.get('final_message')}")
                elif status == "error":
                    print(f"\nJules advisory test errored (advisory only, not blocking): {jules_result.get('reason')}")
                else:
                    print(f"\nJules advisory test finished with status: {status} (advisory only, not blocking)")
                log.info("[%s] Jules advisory test result: %s", state["run_id"], jules_result)

    if state["status"] == "stopped_on_failure":
        unresolved = [f for f in state.get("regression_flags", []) if not f["resolved"]]
        if unresolved:
            # Each flag bundles a LIST of regressed items (a single later
            # item can revert several earlier ones at once), not one
            # task_id/target directly on the flag -- found for real
            # 2026-08-13, crashed here with KeyError the first time this
            # code path actually fired against a real multi-item regression.
            reg_ids = ', '.join(
                f"{b['task_id']}({b['target']})"
                for f in unresolved
                for b in f["regressed_items"]
            )
            after_ids = ', '.join(str(f['after_task_id']) for f in unresolved)
            print(
                f"\nStopped: regression flag(s) on task(s): {reg_ids} triggered by {after_ids}. "
                f"See logs/escalation_{unresolved[0]['after_task_id']}-regression-check.md. "
                f"Fix it manually, then resume with: triapi dispatch {state['run_id']}"
            )
        else:
            last = state["results"][-1]
            print(
                f"\nStopped: '{last['item']}' could not be resolved automatically. "
                f"See logs/escalation_{last['task_id']}.md for details. Fix it manually, "
                f"then resume with: triapi dispatch {state['run_id']}"
            )


def cmd_dispatch(run_id: str, background: bool) -> None:
    state = dispatcher.load_run(run_id)
    # self_fix_drafted is intentionally NOT accepted — only self-fix approve
    # flips a queued self-fix run to planned / dispatchable.
    if state["status"] not in ("planned", "dispatching", "stopped_on_failure"):
        log.warning("[%s] Dispatch refused: status=%s", run_id, state["status"])
        print(f"Run {run_id} is not ready to dispatch (status: {state['status']}).")
        if state["status"] in ("planning", None):
            print(f"Finish planning first: triapi plan is still in progress for this run.")
        elif state["status"] == "self_fix_drafted":
            print(f"Approve it first: triapi self-fix approve <bug_id-or-run_id>")
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
    # Snapshot the Ollama service state once per dispatch run, before Tier 4
    # work, so the service can be restored to exactly this state on exit. A
    # snapshot failure must never block dispatch, so default to None on error.
    tiers_cfg = None
    ollama_snapshot = None
    snapshot_ollama_host = None
    try:
        tiers_cfg = load_tiers()
        if tiers_cfg["tier_4_worker"].get("provider") == "ollama":
            snapshot_ollama_host = tiers_cfg["tier_4_worker"]["endpoint"]
            ollama_snapshot = resource_guard.snapshot_ollama_state(ollama_host=snapshot_ollama_host)
    except Exception as exc:
        snapshot_ollama_host = None
        log.warning("Could not snapshot Ollama state before dispatch: %s", exc)

    # Unload unused Ollama models if configured
    if load_unload_ollama_models_flag():
        try:
            if tiers_cfg is None:
                tiers_cfg = load_tiers()
            if tiers_cfg["tier_4_worker"].get("provider") == "ollama":
                default_model_key = tiers_cfg["tier_4_worker"]["default_model"]
                keep_model = tiers_cfg["tier_4_worker"].get("models", {}).get(default_model_key, default_model_key)
                ollama_host = tiers_cfg["tier_4_worker"]["endpoint"]
                unloaded = resource_guard.unload_other_ollama_models(keep_model=keep_model, ollama_host=ollama_host)
                log.info("Unloaded other Ollama models for this dispatch: %s", unloaded)
        except Exception as exc:
            log.warning("Could not unload other Ollama models before dispatch: %s", exc)
    crash: tuple[Exception, object] | None = None
    bug_path: Path | None = None
    try:
        llm_client.probe_models()
        _breakdown_and_dispatch(state)
    except Exception as exc:
        bug_path = self_fix.capture_crash(exc, run_id=run_id, context="cmd_dispatch:foreground")
        crash = (exc, exc.__traceback__)
    finally:
        if snapshot_ollama_host is not None:
            resource_guard.restore_ollama_state(ollama_snapshot, ollama_host=snapshot_ollama_host)
        resource_guard.resume_services(paused)

    if crash is not None:
        exc, original_tb = crash
        # Queue only after resource-competing services have resumed. Planning
        # can take minutes and must not extend the resource_guard critical section.
        is_self_fix_run = "self_fix_bug_report" in state
        try:
            self_fix_enabled = load_tiers().get("self_fix", {}).get("enabled", True)
        except Exception as config_exc:
            self_fix_enabled = False
            log.warning(
                "[%s] Could not load self-fix configuration during crash recovery: %s",
                run_id,
                config_exc,
            )
        if is_self_fix_run:
            log.warning(
                "[%s] Crash occurred inside a self-fix run itself; not auto-queuing a nested "
                "self-fix (bug report saved: %s)",
                run_id,
                bug_path,
            )
        elif not self_fix_enabled:
            log.info("[%s] Self-fix auto-queue disabled (bug report saved: %s)", run_id, bug_path)
        elif bug_path is not None:
            try:
                queued = self_fix.queue_self_fix(bug_path)
                log.info("[%s] Self-fix queued: %s", run_id, queued)
            except Exception as queue_exc:
                log.warning("[%s] Self-fix auto-queue failed: %s", run_id, queue_exc)
        raise exc.with_traceback(original_tb)


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
    unresolved = [f for f in state.get("regression_flags", []) if not f["resolved"]]
    if unresolved:
        print(f"\n{len(unresolved)} unresolved regression flag(s):")
        for f in unresolved:
            for b in f["regressed_items"]:
                print(f"  {b['task_id']}({b['target']}) => logs/escalation_{f['after_task_id']}-regression-check.md")


def cmd_list() -> None:
    runs = dispatcher.list_runs()
    if not runs:
        print("No runs yet.")
        return
    for r in runs:
        started = time.strftime("%Y-%m-%d %H:%M", time.localtime(r["started_at"]))
        prompt_preview = r["prompt"][:60] + ("..." if len(r["prompt"]) > 60 else "")
        print(f"{r['run_id']}  [{r['status']:>18}]  {started}  {prompt_preview}")


def _find_self_fix_run(bug_id: str) -> dict | None:
    """Resolve a bug_id (report stem) or run_id to a queued/approved self-fix run."""
    # Direct run_id hit.
    try:
        state = dispatcher.load_run(bug_id)
        if "self_fix_bug_report" in state or state.get("status") == "self_fix_drafted":
            return state
    except FileNotFoundError:
        pass

    bug_path = self_fix.BUGS_DIR / f"{bug_id}.json"
    for summary in dispatcher.list_runs():
        try:
            full = dispatcher.load_run(summary["run_id"])
        except FileNotFoundError:
            continue
        ref = full.get("self_fix_bug_report") or ""
        if not ref:
            continue
        if Path(ref).name == f"{bug_id}.json" or Path(ref).stem == bug_id:
            return full
        if bug_path.exists() and Path(ref).resolve() == bug_path.resolve():
            return full
    return None


def _resolve_bug_report(bug_id: str) -> Path | None:
    """Resolve a report stem without allowing traversal outside BUGS_DIR."""
    candidate = (self_fix.BUGS_DIR / f"{bug_id}.json").resolve()
    if not candidate.is_relative_to(self_fix.BUGS_DIR.resolve()):
        return None
    return candidate if candidate.is_file() else None


def cmd_self_fix_list() -> None:
    """List unqueued bug reports and drafted-but-unapproved self-fix runs."""
    runs = []
    referenced = set()
    for summary in dispatcher.list_runs():
        try:
            full = dispatcher.load_run(summary["run_id"])
        except FileNotFoundError:
            continue
        ref = full.get("self_fix_bug_report")
        if ref:
            referenced.add(Path(ref).resolve())
            referenced.add(Path(ref).name)
            referenced.add(Path(ref).stem)
        if full.get("status") == "self_fix_drafted":
            runs.append(full)

    print("Unqueued bug reports:")
    bugs = sorted(self_fix.BUGS_DIR.glob("*.json")) if self_fix.BUGS_DIR.exists() else []
    shown = 0
    for path in bugs:
        if path.resolve() in referenced or path.name in referenced or path.stem in referenced:
            continue
        print(f"  {path.stem}")
        shown += 1
    if shown == 0:
        print("  (none)")

    print("Drafted self-fix runs (awaiting approve):")
    if not runs:
        print("  (none)")
        return
    for state in runs:
        print(f"  {state['run_id']}  {state.get('prompt', '')[:80]}")


def cmd_self_fix_show(bug_id: str) -> None:
    """Print a bug report and any drafted plan text."""
    bug_path = _resolve_bug_report(bug_id)
    state = _find_self_fix_run(bug_id)
    if state and "self_fix_bug_report" in state:
        linked = Path(state["self_fix_bug_report"]).expanduser()
        try:
            linked = linked.resolve()
        except OSError:
            linked = None
        else:
            if (
                linked.is_relative_to(self_fix.BUGS_DIR.resolve())
                and linked.is_file()
            ):
                bug_path = linked

    if bug_path is not None and bug_path.is_file():
        import json
        data = json.loads(bug_path.read_text())
        print(f"Bug report: {bug_path.name}")
        print(json.dumps(data, indent=2))
    else:
        print(f"No bug report file found for id {bug_id!r} under {self_fix.BUGS_DIR}")

    if state is None:
        print("\nNo drafted self-fix run linked to this id.")
        return
    print(f"\nLinked run: {state['run_id']}  status={state['status']}")
    print(state.get("plan_text") or "(no plan_text)")


def cmd_self_fix_queue(bug_id: str) -> None:
    """Draft a self-fix run for a captured but unqueued bug report."""
    bug_path = _resolve_bug_report(bug_id)
    if bug_path is None:
        print(f"No bug report file found for id {bug_id!r} under {self_fix.BUGS_DIR}")
        raise SystemExit(1)
    existing = _find_self_fix_run(bug_id)
    if existing is not None:
        print(f"Bug {bug_id!r} is already linked to run {existing['run_id']}.")
        return
    result = self_fix.queue_self_fix(bug_path)
    if result.get("status") != "queued":
        print(f"Could not draft self-fix: {result.get('reason', result.get('status'))}")
        raise SystemExit(1)
    print(f"Self-fix drafted. Linked run: {result['run_id']}")
    print(f"Review it: triapi self-fix show {bug_id}")


def cmd_self_fix_approve(bug_id: str) -> None:
    """Flip a self_fix_drafted run to planned (dispatchable)."""
    state = _find_self_fix_run(bug_id)
    if state is None:
        print(f"No self-fix run found for {bug_id!r}")
        raise SystemExit(1)
    if state["status"] not in ("self_fix_drafted", "planned"):
        print(f"Run {state['run_id']} is not approvable (status: {state['status']})")
        raise SystemExit(1)
    state["status"] = "planned"
    dispatcher.save_run(state)
    print(f"\nPlan approved.")
    print(f"Run it: triapi dispatch {state['run_id']}")


def cmd_tech_debt(project_dir: str) -> None:
    entries = tech_debt.read_tech_debt_entries()
    filtered_entries = [entry for entry in entries if not tech_debt.check_staleness(entry)]
    
    synthetic_state = {
        "run_id": str(uuid.uuid4()),
        "project_dir": project_dir,
        "status": "planned",
        "plan_text": "",
        "breakdown": {
            "phases": [
                {
                    "name": "Tech Debt",
                    "items": [
                        {
                            "description": f"Fix {entry['filepath']}",
                            "target": entry["filepath"],
                            "build_cmd": f"# Add your build command here to fix {entry['filepath']}",
                            "verify_only": False,
                            "context_files": []
                        }
                        for entry in filtered_entries
                    ]
                }
            ]
        },
        "results": [],
        "regression_flags": []
    }
    
    dispatcher.save_run(synthetic_state)
    dispatcher.dispatch(synthetic_state)


def main():
    parser = argparse.ArgumentParser(description="TriAPI natural-language pipeline entry point")
    sub = parser.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser("plan", help="interactively define and approve an execution plan")
    p_plan.add_argument("prompt")
    p_plan.add_argument("--project-dir", default=".")
    p_plan.add_argument(
        "--refactor", action="store_true",
        help="override the one-plan-per-repo gate: proceed even if this repo's AGENTS.md "
        "has an incomplete TriAPI plan, because this goal is a deliberate refactor/pivot",
    )

    p_dispatch = sub.add_parser("dispatch", help="execute an approved plan")
    p_dispatch.add_argument("run_id")
    p_dispatch.add_argument("--background", action="store_true", help="run detached, safe against SSH disconnects")
    p_dispatch.add_argument("--no-tier1", action="store_true", help="force Tier 1 (Claude Code CLI) off for this run only, without editing config/tiers.yaml (sets TRIAPI_NO_TIER1=1)")

    p_status = sub.add_parser("status", help="show progress of a run")
    p_status.add_argument("run_id")

    sub.add_parser("list", help="list all runs")

    p_self_fix = sub.add_parser("self-fix", help="review/approve TriAPI-internal auto-drafted bug fixes")
    selffix_sub = p_self_fix.add_subparsers(dest="self_fix_action", required=True)
    selffix_sub.add_parser("list", help="list captured bugs and drafted/unapproved self-fix runs")
    p_sf_queue = selffix_sub.add_parser("queue", help="draft a self-fix run for a captured bug")
    p_sf_queue.add_argument("bug_id")
    p_sf_show = selffix_sub.add_parser("show", help="show a bug report and its drafted plan")
    p_sf_show.add_argument("bug_id")
    p_sf_approve = selffix_sub.add_parser("approve", help="approve a drafted self-fix run for dispatch")
    p_sf_approve.add_argument("bug_id")

    p_tech_debt = sub.add_parser("tech-debt", help="process tech debt entries")
    p_tech_debt.add_argument("--project-dir", required=True, help="the project directory containing TECH_DEBT.md")

    args = parser.parse_args()

    if args.command == "plan":
        cmd_plan(args.prompt, args.project_dir, args.refactor)
    elif args.command == "dispatch":
        if args.no_tier1:
            os.environ["TRIAPI_NO_TIER1"] = "1"
        cmd_dispatch(args.run_id, args.background)
    elif args.command == "status":
        cmd_status(args.run_id)
    elif args.command == "self-fix":
        if args.self_fix_action == "list":
            cmd_self_fix_list()
        elif args.self_fix_action == "queue":
            cmd_self_fix_queue(args.bug_id)
        elif args.self_fix_action == "show":
            cmd_self_fix_show(args.bug_id)
        elif args.self_fix_action == "approve":
            cmd_self_fix_approve(args.bug_id)
    elif args.command == "list":
        cmd_list()
    elif args.command == "tech-debt":
        cmd_tech_debt(args.project_dir)


if __name__ == "__main__":
    main()
