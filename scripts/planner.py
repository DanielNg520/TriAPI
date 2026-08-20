"""Tier 1 (as Planner): an interactive conversation with Claude to turn a
natural-language goal into an execution plan the user actually approves,
before anything gets built or costs money.

Distinct from tier1_escalate.py, which uses Claude Code CLI as a repair
tier for a single already-known-broken file. This module uses Claude in
the strategic-planner role from the original design: given a rough goal
and read-only access to a project directory, it proposes a plan, the user
gives feedback or approves it, and only the approved plan text is ever
handed to Tier 2 for breakdown and dispatch. Getting the plan right here
is cheap (subscription quota); getting it wrong and letting the pipeline
build the wrong thing is what actually costs time and money.

Read-only by design: the planner is only allowed Read/Glob/Grep tools, so
it can inspect the project and any referenced plan.md, but cannot edit
files or run commands itself -- planning and execution are kept separate.

Each turn is a separate `claude -p` call chained via --resume so the
conversation has real memory across turns (verified: a fact stated in one
call is correctly recalled in a --resume'd follow-up call).

Must only be called after budget_guard.check_tier1_ok().

Note: the downstream Tier 3 (DeepSeek) leg is billed at DeepSeek's peak rate
during 06:00-10:00 UTC; `in_tier3_deepseek_peak_utc()` exposes this window so
plans can be priced/scheduled with that cost in mind.
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.budget_guard import check_tier1_ok
from scripts.tri_logging import get_logger

log = get_logger("planner")

# Tier 3 runs on DeepSeek, whose billing has a peak window of 06:00-10:00 UTC.
# Tier 1 planning itself is charged to subscription quota, but the expensive
# downstream tier must avoid that window; the constant and helper below make the
# window explicit and testable so callers can price/schedule a plan without
# re-deriving the rule.
TIER3_DEEPSEEK_PEAK_UTC_START = 6  # inclusive
TIER3_DEEPSEEK_PEAK_UTC_END = 10  # exclusive


def in_tier3_deepseek_peak_utc(now: datetime | None = None) -> bool:
    """Return True when `now` falls in DeepSeek's Tier 3 peak billing window.

    The window is 06:00-10:00 UTC. `now` defaults to the current time in UTC;
    a tz-aware datetime is converted to UTC, a naive datetime is assumed UTC.
    Example: LA local 2026-08-19T23:14:07.869655-07:00 is UTC
    2026-08-20T06:14:07.869655+00:00, which is inside the window -> True.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)
    return TIER3_DEEPSEEK_PEAK_UTC_START <= now.hour < TIER3_DEEPSEEK_PEAK_UTC_END

SYSTEM_PROMPT = (
    "You are a software architect having a conversation with the user to define "
    "an execution plan, before any of it gets built. Given a natural-language "
    "goal and read-only access to a project directory, propose a clear, "
    "actionable execution plan as markdown: a numbered list of phases, and "
    "within each phase a checklist of concrete steps. Every step MUST be a "
    "markdown checkbox line starting with '- [ ] ' (unchecked) -- this is "
    "how the pipeline tracks completion later, so never omit it and never "
    "pre-check a box. Each step must name the "
    "specific file (one file per step) that needs creating or changing, what "
    "change is needed -- including every concrete technical requirement "
    "(language/standard version, library versions, exact interfaces, exact "
    "expected output) so nothing is lost if this step is later summarized by "
    "someone else -- and the exact shell command to build/verify it. If the "
    "goal references a plan.md or similar file inside the project, read it and "
    "follow it strictly rather than inventing your own direction.\n\n"
    "A step may instead be an explicit git operation (clone a repo, pull, or "
    "push/commit changes) when the goal actually calls for one -- state exactly "
    "what: the repo URL for a clone, or for a push, the commit message and "
    "(only if the goal specifies it) which branch. Do not add a git step the "
    "goal didn't ask for. Note for pushes: this pipeline will never push "
    "directly to main/master unless that exact branch is explicitly named in "
    "the step -- otherwise it creates a new branch, so say so in the plan if "
    "that matters for the goal.\n\n"
    "You do NOT have write access -- do not attempt to write files, and do not "
    "comment on the write failing.\n\n"
    "This is a back-and-forth conversation, not a one-shot answer: if anything "
    "about the goal is ambiguous, underspecified, or you need a decision from "
    "the user before proposing a solid plan, ask one focused question instead "
    "of guessing. Otherwise, propose your best plan (or a revised plan, if the "
    "user gave feedback on a previous version) in the exact phase/checklist "
    "markdown format described above. Every response must be ONLY the question "
    "or the plan -- no unrelated commentary, no offers of unrelated next steps.\n\n"
    "This box's installed `sops` is version 3.8.1 (confirmed via `sops --version`), "
    "which has NO `set` subcommand — `sops --help`'s COMMANDS list is only "
    "`exec-env`/`exec-file`/`publish`/`keyservice`/`groups`/`updatekeys`/`help`. "
    "Any plan step editing a secrets file in place MUST use the `--set` flag on the "
    "default (edit-mode) invocation, never the `sops set FILE key value` subcommand "
    "form. Concrete working syntax: for a nested key, `sops --set '[\"key\"][0] \"value\"' "
    "FILE`; for a top-level key, `sops --set '[\"key\"] \"value\"' FILE`. "
    "Never generate `sops set FILE key value` — that subcommand does not exist on this "
    "box's sops 3.8.1."
)


def plan_turn(message: str, project_dir: str, session_id: str | None) -> dict:
    """One turn of the interactive planning conversation.

    Pass session_id=None for the first turn; pass back the session_id this
    returns for every subsequent turn so the conversation has memory.
    """
    guard = check_tier1_ok()
    if not guard["ok"]:
        log.warning("Planning turn skipped: %s", guard["reason"])
        return {"status": "skipped", "reason": guard["reason"]}

    log.info("Planning turn: project_dir=%s resume=%s message_len=%d", project_dir, bool(session_id), len(message))

    cmd = [
        "claude",
        "-p",
        message,
        "--output-format",
        "json",
        "--allowedTools",
        "Read,Glob,Grep",
        "--add-dir",
        project_dir,
        "--system-prompt",
        SYSTEM_PROMPT,
    ]
    if session_id:
        cmd += ["--resume", session_id]

    timeout_s = 600
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_s, cwd=project_dir, stdin=subprocess.DEVNULL
        )
    except subprocess.TimeoutExpired:
        log.error("Planning turn timed out after %ds (project_dir=%s)", timeout_s, project_dir)
        return {"status": "error", "reason": f"Planning turn timed out after {timeout_s}s"}
    if result.returncode != 0:
        log.error("Planning turn failed (returncode=%d): %s", result.returncode, result.stderr.strip()[:500])
        return {"status": "error", "reason": result.stderr.strip()}

    data = json.loads(result.stdout)
    if data.get("is_error"):
        log.error("Planning turn returned an error: %s", str(data.get("result"))[:500])
        return {"status": "error", "reason": data.get("result", "unknown Claude error")}

    log.info(
        "Planning turn ok: session_id=%s notional_cost=$%.4f response_len=%d",
        data["session_id"], data.get("total_cost_usd", 0.0), len(data["result"]),
    )
    return {
        "status": "ok",
        "text": data["result"],
        "session_id": data["session_id"],
        "notional_cost_usd": data.get("total_cost_usd", 0.0),
    }
