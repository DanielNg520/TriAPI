"""Ties Tier 4 -> Tier 3 -> Tier 2 -> Tier 1 -> human handoff together.

Tier 4 (Ollama) drafts AND rebuilds each attempt. Once it escalates, Tiers
3/1/2 only patch the file and hand back to a plain rebuild (scripts.tier4_worker.run_build)
-- they must NOT trigger another Ollama draft, which would overwrite their fix.

State is file-backed (logs/state/<task_id>.json) so this can be re-entered
across process invocations, matching how Tier 4 is expected to run.
"""

import argparse
import difflib
import fnmatch
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.budget_guard import check_tier1_ok, check_tier1_manager_ok, check_tier2_ok, check_tier3_peak_hours_ok, resolve_deepseek_tier
from scripts.config_loader import load_tiers
from scripts.cost_report import format_report, report
from scripts.state import clear_state, read_state, record_failure
from scripts.tier1_escalate import escalate as tier1_escalate
from scripts.tier2_escalate import escalate as tier2_escalate
from scripts.tier3_escalate import escalate as tier3_escalate
from scripts.tier4_worker import build_context_blob
from scripts.tier4_worker import run as tier4_run
from scripts.tier4_worker import run_build
from scripts.tri_logging import get_logger
from scripts import critique
from scripts import lessons
from scripts import librarian_escalate

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


def _read_target_text(path: str) -> str:
    try:
        return Path(path).read_text()
    except Exception:
        return ""


def _critique_and_maybe_revise(task_id: str, resolved_target: str, description: str,
                                tier_name: str, escalate_fn, build_cmd: str, workdir: str,
                                context_blob: str, config: dict, before_content: str) -> None:
    """Advisory diff-quality critique after a Tier 3/1/2 fix already passed
    rebuild. Never changes resolved_by / never calls human_handoff / never
    forces fall-through to the next tier. On a below-threshold score, makes
    at most ``max_revision_attempts`` revision passes with critique feedback
    folded into revision_note; reverts if a revision breaks the build.
    Any unexpected exception is swallowed so a passing item cannot be aborted."""
    try:
        _critique_and_maybe_revise_inner(
            task_id, resolved_target, description, tier_name, escalate_fn,
            build_cmd, workdir, context_blob, config, before_content,
        )
    except Exception as exc:
        log.warning("[%s] Critique/revision failed unexpectedly for %s: %s", task_id, tier_name, exc)


def _critique_and_maybe_revise_inner(task_id: str, resolved_target: str, description: str,
                                tier_name: str, escalate_fn, build_cmd: str, workdir: str,
                                context_blob: str, config: dict, before_content: str) -> None:
    critique_cfg = config.get("critique", {})
    if not critique_cfg.get("enabled", False):
        return
    if tier_name not in critique_cfg.get("applies_to_tiers", []):
        return
    if critique_cfg.get("critic", "tier_1") != "tier_1":
        log.warning("[%s] Unsupported critique critic %r; skipping", task_id, critique_cfg.get("critic"))
        return
    try:
        max_revision_attempts = int(critique_cfg.get("max_revision_attempts", 1))
        threshold = int(critique_cfg.get("score_threshold", 7))
    except (TypeError, ValueError):
        log.warning("[%s] Invalid critique numeric configuration; skipping critique", task_id)
        return
    if max_revision_attempts < 0:
        log.warning("[%s] Invalid max_revision_attempts %s; skipping critique", task_id, max_revision_attempts)
        return

    after_content = _read_target_text(resolved_target)
    diff_text = "".join(
        difflib.unified_diff(
            before_content.splitlines(keepends=True),
            after_content.splitlines(keepends=True),
            fromfile=resolved_target,
            tofile=resolved_target,
        )
    )
    if not diff_text.strip():
        return

    try:
        result = critique.critique_diff(
            task_id,
            Path(resolved_target).name,
            description,
            diff_text,
            tier_name,
            score_threshold=threshold,
        )
    except Exception as exc:
        log.warning("[%s] Critique failed unexpectedly for %s: %s", task_id, tier_name, exc)
        return
    if result.get("status") != "ok":
        level = log.warning if result.get("status") == "error" else log.info
        level("[%s] Critique %s for %s: %s", task_id, result.get("status"), tier_name, result.get("reason"))
        return

    try:
        score = int(result.get("score"))
    except (TypeError, ValueError):
        log.warning("[%s] Critique returned an invalid score; keeping passing fix", task_id)
        return
    issues = result.get("issues") or []
    if score >= threshold:
        log.info("[%s] Critique passed (score=%s)", task_id, score)
        return
    if not issues:
        log.warning(
            "[%s] Critique scored %s below threshold but supplied no actionable issues; "
            "keeping original passing fix",
            task_id,
            score,
        )
        return
    if max_revision_attempts < 1:
        log.warning(
            "[%s] Critique flagged %s's fix (score=%s/10): %s -- no revision "
            "(max_revision_attempts=0); keeping original passing fix",
            task_id, tier_name, score, issues,
        )
        return

    log.warning(
        "[%s] Critique flagged %s's fix (score=%s/10): %s -- attempting up to %s revision pass(es)",
        task_id, tier_name, score, issues, max_revision_attempts,
    )
    pre_revision_content = after_content
    revision_note = "; ".join(str(i) for i in issues)

    def _revert() -> None:
        try:
            Path(resolved_target).write_text(pre_revision_content)
        except OSError as revert_exc:
            log.warning("[%s] Could not revert after failed revision: %s", task_id, revert_exc)

    for attempt in range(1, max_revision_attempts + 1):
        try:
            rev = escalate_fn(
                task_id,
                resolved_target,
                context_blob=context_blob,
                revision_note=revision_note,
                description=description,
            )
        except Exception as exc:
            log.warning(
                "[%s] Critique revision attempt %s/%s raised %s -- reverting",
                task_id, attempt, max_revision_attempts, exc,
            )
            _revert()
            continue
        if rev.get("status") != "fix_applied":
            log.warning(
                "[%s] Critique revision attempt %s/%s failed (%s) -- reverting",
                task_id, attempt, max_revision_attempts, rev.get("reason") or rev.get("status"),
            )
            _revert()
            continue

        try:
            ok, _output = run_build(build_cmd, workdir)
        except Exception as exc:
            log.warning(
                "[%s] Critique revision rebuild raised %s -- reverting",
                task_id, exc,
            )
            _revert()
            continue
        if not ok:
            _revert()
            log.warning(
                "[%s] Critique revision attempt %s/%s broke the build -- reverted",
                task_id, attempt, max_revision_attempts,
            )
            continue

        log.info(
            "[%s] Critique revision %s/%s applied and build still passes",
            task_id, attempt, max_revision_attempts,
        )
        return

    log.warning(
        "[%s] Critique revisions exhausted (%s) -- kept original passing fix",
        task_id, max_revision_attempts,
    )


def human_handoff(
    task_id: str,
    reason: str,
    detail: str = "",
    *,
    component: str = "",
) -> None:
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
    try:
        lessons.add_lesson(
            bug_description=f"Task '{task_id}' needs human review",
            what_went_wrong=reason,
            fix_description="(unresolved — needs human review; see " + str(summary_path) + ")",
            category="unresolved_pattern",
            component=component or task_id,
            tags=["human_handoff"],
            path=lessons.HANDOFF_LESSONS_PATH,
        )
    except Exception as exc:
        log.warning("[%s] Could not record handoff lesson: %s", task_id, exc)
    print(f"[HUMAN HANDOFF] Task '{task_id}' needs manual review: {reason}")
    print(f"[HUMAN HANDOFF] See {summary_path}")
    log.warning("[%s] Human handoff: %s", task_id, reason)


def verify_task(task_id: str, build_cmd: str, workdir: str = ".") -> dict:
    """For plan items with nothing to draft/change (e.g. "run the test
    suite", "grep for no remaining call sites") -- runs build_cmd against
    files as they already are. Never invokes Tier 4's draft step, which
    would otherwise overwrite a file that doesn't need editing, and never
    escalates to Tier 1/2/3: there's no file for an AI tier to sensibly
    "fix" for a pure check -- if it fails, the real bug is presumably in
    whatever an earlier item changed, not in this verification command
    itself, so this goes straight to human_handoff on the first failure."""
    log.info("[%s] verify_task starting: %s", task_id, build_cmd)
    # A verify_only step is a single one-shot check with no per-tier-attempt
    # budget to protect (unlike a draft/build loop that retries repeatedly),
    # so it can afford a longer timeout than run_build()'s 300s default --
    # e.g. this repo's own full test suite legitimately takes 166-330s
    # (observed live, 2026-08-25), leaving no headroom at 300s and tripping
    # a false human_handoff on ordinary load variance, not a real failure
    # (found for real 2026-08-25 while dispatching run 20260825-154633-8927c3:
    # a 191-test run hit exactly this wall at 300s, independently reconfirmed
    # passing in 230s moments later). Raised to 600s for real headroom as
    # this repo's suite keeps growing; run_build()'s own 300s default is
    # unaffected since draft/build-loop tiers retry rather than needing one
    # long timeout to hold. Originally 120s until 2026-08-11's identical
    # discovery (`./run_tests.sh` crashing the whole dispatch process).
    ok, output = run_build(build_cmd, workdir, timeout=600)
    cost_rep = report(task_id)
    if ok:
        clear_state(task_id)
        log.info("[%s] verify_task succeeded", task_id)
        return {"status": "success", "resolved_by": "verify", "cost_report": cost_rep}

    record_failure(task_id, output)
    detail = f"**Verification command:** `{build_cmd}`\n\n**Output:**\n```\n{output}\n```"
    human_handoff(task_id, "verification failed (no file to draft/fix for this step)", detail)
    return {"status": "human_handoff", "resolved_by": None, "cost_report": cost_rep}


def _is_doc_target(target: str, target_globs: list[str]) -> bool:
    """Returns True if target matches any of the Tier 5 librarian
    target_globs (e.g. '*.md', 'docs/*.rst'), routing it to the doc-fix
    pipeline instead of the code-fix pipeline."""
    if not target_globs:
        return False
    return any(fnmatch.fnmatch(target, pat) for pat in target_globs)


def _peak_hour_guard(task_id: str, tier_key: str, deepseek_tier: str | None) -> dict | None:
    """Slot-conditional DeepSeek peak-hour gate.

    Fires check_tier3_peak_hours_ok() only when ``tier_key`` matches the
    resolved DeepSeek tier, so the gate follows DeepSeek wherever it sits in
    tiers.yaml (today: tier_3_debugger; after a manual reassignment it tracks
    the new slot automatically). On refusal returns the guard dict (ok=False);
    callers take today's Tier-3 refusal path -- log a skip and fall through
    to the next escalation tier. Returns None when this site isn't
    DeepSeek-gated, meaning no check is needed and the escalation attempt
    proceeds directly.
    """
    if tier_key != deepseek_tier:
        return None
    return check_tier3_peak_hours_ok()


def run_task(task_id: str, description: str, target: str, workdir: str = ".", build_cmd: str | None = None, tier4_model: str | None = None, context_files: list[str] | None = None, skip_tier4: bool = False) -> dict:
    tiers_config = load_tiers()
    deepseek_tier = resolve_deepseek_tier(tiers_config)
    build_cmd = build_cmd or " && ".join(tiers_config["tier_4_worker"]["build_commands"])

    # Tier 5 (librarian): for standalone single-target runs whose target is a
    # doc file matched by tier_5_librarian.target_globs, delegate entirely to
    # librarian_escalate.run() -- which handles the full doc-fix pipeline --
    # and return its result through the normal cost-report path below.
    librarian_cfg = tiers_config.get("tier_5_librarian")
    if librarian_cfg and librarian_cfg.get("enabled", True) and _is_doc_target(target, librarian_cfg.get("target_globs", [])):
        log.info("[%s] Tier 5 (librarian) routing for doc target %s", task_id, target)
        result = librarian_escalate.run(
            task_id, description, target, workdir=workdir
        )
        cost_rep = report(task_id)
        return {
            "status": result.get("status", "error"),
            "resolved_by": result.get("resolved_by"),
            "cost_report": cost_rep,
        }

    # tier4_run resolves target against workdir internally; tiers 1-3 don't
    # take a workdir argument, so resolve once here and pass the full path.
    target_arg = Path(target)
    resolved_target = str(target_arg if target_arg.is_absolute() else Path(workdir) / target_arg)

    # Built once and reused across every tier attempt: other repo files the
    # item's description references (e.g. "seeded from X"), read in read-only
    # so drafting is grounded in what's actually in the repo instead of
    # guessing. Content is fixed per item, so this is fine to reuse across
    # Tier 4 retries and every escalation tier without re-reading each time.
    context_blob = build_context_blob(context_files or [], workdir)

    resolved_by = None
    log.info("[%s] run_task starting: target=%s workdir=%s context_files=%s skip_tier4=%s", task_id, target, workdir, context_files, skip_tier4)

    # Tier 4: draft + build loop, until success or escalate. Skipped entirely
    # when skip_tier4 is set -- e.g. an item whose target already exceeds
    # Tier 4's context ceiling (dispatcher._enforce_file_size_ceiling) is
    # something Tier 4's small local window can never handle, so there is no
    # point spending an attempt (and risking its known ~300s timeout) before
    # escalating; go straight to Tier 3, whose cloud context window is far
    # larger. Tier 4 remains the default (skip_tier4=False) for every
    # ordinary item.
    if skip_tier4:
        log.info("[%s] Tier 4 skipped (oversized target); starting at Tier 3", task_id)
    else:
        while True:
            try:
                result = tier4_run(task_id, description, target, workdir, build_cmd, tier4_model, context_blob)
            except Exception as e:
                # An exception here (e.g. Ollama connection/read timeout) should
                # crash the pipeline rather than silently escalating to lower
                # tiers that can't fix an Ollama connectivity problem.
                log.warning("[%s] Tier 4 raised %s; crashing pipeline", task_id, e)
                record_failure(task_id, str(e))
                raise
            log.info("[%s] Tier 4 attempt: %s (consecutive_failures=%s)", task_id, result["status"], result.get("consecutive_failures"))
            if result["status"] == "success":
                resolved_by = "tier_4"
                break
            if result["status"] != "build_failed":
                # Covers "escalate" as well as unexpected statuses returned by
                # tier4_run (e.g. "error" from a timed-out Ollama request). Only
                # "build_failed" should loop around for another Tier 4 attempt.
                log.warning("[%s] Tier 4 returned status %s; escalating", task_id, result["status"])
                break

    if resolved_by is None:
        # Tier 3: DeepSeek v4 Flash off-peak; OpenRouter's free Nemotron
        # model during DeepSeek's peak-billing window instead of being
        # skipped outright -- tier3_escalate.escalate() resolves which one
        # via budget_guard.resolve_peak_conditional(tiers_config[
        # "tier_3_debugger"]) internally, so this tier now runs every item
        # regardless of time of day.
        before_content = _read_target_text(resolved_target)
        result3 = tier3_escalate(
            task_id, resolved_target, context_blob=context_blob, description=description
        )
        if result3.get("status") == "timeout":
            log.warning("[%s] Tier 3 timed out; soft-escalating to Tier 2: %s", task_id, result3.get("reason"))
        if result3.get("status") == "error":
            raise RuntimeError(f"Tier 3 failed: {result3.get('reason')}")
        if result3.get("status") == "fix_rejected":
            log.warning("[%s] Tier 3 fix rejected: %s", task_id, result3.get("reason"))
        if result3.get("status") == "fix_applied" and _rebuild_after_patch(task_id, build_cmd, workdir):
            resolved_by = "tier_3"
            _critique_and_maybe_revise(task_id, resolved_target, description, "tier_3",
                                        tier3_escalate, build_cmd, workdir, context_blob, tiers_config, before_content)

    if resolved_by is None:
        # Tier 2: DeepSeek v4 Pro off-peak; agy/Gemini 3.7 Flash during
        # DeepSeek's peak-billing window instead of being skipped outright --
        # tier2_escalate.escalate() resolves which one via
        # budget_guard.resolve_peak_conditional(tiers_config[
        # "tier_2_manager"]) internally. Tried before Tier 1 so that Claude
        # (subscription-backed, and the strongest automated repair tier)
        # stays reserved as the last automated attempt before human handoff,
        # not spent on problems Tier 2 might still resolve.
        guard2 = check_tier2_ok()
        if guard2["ok"]:
            before_content = _read_target_text(resolved_target)
            result2 = tier2_escalate(
                task_id, resolved_target, context_blob=context_blob, description=description
            )
            if result2.get("status") == "error":
                raise RuntimeError(f"Tier 2 failed: {result2.get('reason')}")
            if result2.get("status") == "fix_rejected":
                log.warning("[%s] Tier 2 fix rejected: %s", task_id, result2.get("reason"))
            if result2.get("status") == "fix_applied" and _rebuild_after_patch(task_id, build_cmd, workdir):
                resolved_by = "tier_2"
                _critique_and_maybe_revise(task_id, resolved_target, description, "tier_2",
                                            tier2_escalate, build_cmd, workdir, context_blob, tiers_config, before_content)
        else:
            print(f"[BUDGET GUARD] Tier 2 skipped: {guard2['reason']}")

    if resolved_by is None:
        # Tier 1: Claude Code CLI (budget-guarded), last automated tier.
        guard1 = check_tier1_ok()
        guard1m = check_tier1_manager_ok(tiers_config)
        peak1 = _peak_hour_guard(task_id, "tier_1_manager", deepseek_tier)
        if peak1 and not peak1["ok"]:
            log.info("[%s] Tier 1 skipped: %s", task_id, peak1["reason"])
        elif guard1["ok"] and guard1m["ok"]:
            before_content = _read_target_text(resolved_target)
            result1 = tier1_escalate(
                task_id, resolved_target, context_blob=context_blob, description=description
            )
            if result1.get("status") == "error":
                raise RuntimeError(f"Tier 1 failed: {result1.get('reason')}")
            if result1.get("status") == "fix_rejected":
                log.warning("[%s] Tier 1 fix rejected: %s", task_id, result1.get("reason"))
            if result1.get("status") == "fix_applied" and _rebuild_after_patch(task_id, build_cmd, workdir):
                resolved_by = "tier_1"
                _critique_and_maybe_revise(task_id, resolved_target, description, "tier_1",
                                            tier1_escalate, build_cmd, workdir, context_blob, tiers_config, before_content)
        elif not guard1["ok"]:
            print(f"[BUDGET GUARD] Tier 1 skipped: {guard1['reason']}")
        else:
            print(f"[BUDGET GUARD] Tier 1 skipped: {guard1m['reason']}")

    if resolved_by is None:
        handoff_state = read_state(task_id)
        detail = (
            f"**Consecutive failures recorded:** {handoff_state.get('consecutive_failures')}\n\n"
            f"**Last build error:**\n```\n{handoff_state.get('last_stderr', '')}\n```"
        )
        human_handoff(
            task_id,
            "unresolved after Tier 4 -> Tier 3 -> Tier 2 -> Tier 1",
            detail,
            component=target,
        )
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
    parser.add_argument("--context-file", action="append", default=[], help="other repo file(s) to read for grounding, relative to --workdir; repeatable")
    args = parser.parse_args()

    result = run_task(args.task_id, args.description, args.target, args.workdir, args.build_cmd, args.tier4_model, args.context_file)
    print(json.dumps({"status": result["status"], "resolved_by": result["resolved_by"]}))
    print()
    print(format_report(result["cost_report"]))


if __name__ == "__main__":
    main()
