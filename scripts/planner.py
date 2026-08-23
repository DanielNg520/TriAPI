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

Every provider, including the local Claude CLI, is dispatched through the
single entry point llm_client.execute_llm(); planner.py no longer invokes
`claude -p` or parses its JSON output itself. execute_llm() does not expose
a session identifier, so plan_turn() always returns session_id='stateless'
(no planner-tracked cross-turn session).

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
from scripts import config_loader, llm_client, secrets_loader
from scripts.tier4_worker import build_context_blob
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
    returns for every subsequent turn.

    The provider is read from config (tier_1_planner.provider). For the
    local Claude CLI ('cli'), planner.py shells out to `claude -p` natively
    with tools (Read,Glob,Grep), --output-format json, --add-dir, and
    --resume, parses its JSON output, and falls back to
    llm_client._fallback_request() on failure. Non-'cli' providers and the
    'cli' fallback enrich the prompt with a context blob (AGENTS.md,
    PLAN.md, README.md) since they lack tools, and are dispatched through
    llm_client.execute_llm(). execute_llm() returns no cross-turn session
    identifier, so every turn returns session_id='stateless'.
    """
    guard = check_tier1_ok()
    if not guard["ok"]:
        log.warning("Planning turn skipped: %s", guard["reason"])
        return {"status": "skipped", "reason": guard["reason"]}

    log.info("Planning turn: project_dir=%s resume=%s message_len=%d", project_dir, bool(session_id), len(message))

    tier1 = config_loader.load_tiers().get("tier_1_planner", {})
    provider = tier1.get("provider", "cli")

    return _plan_turn_llm(message, project_dir, session_id, tier1, provider)


def _text_from_claude_json(data) -> str | None:
    """Extract the assistant's text from a parsed `claude --output-format json` object."""
    if isinstance(data, str):
        return data or None
    if not isinstance(data, dict):
        return None
    text = data.get("result")
    if text is None:
        text = data.get("text")
    if text is None:
        content = data.get("content")
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            parts = [
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            text = "".join(parts)
    return text or None


def _extract_claude_result(stdout: str) -> str | None:
    """Pull the assistant's text out of `claude --output-format json` stdout.

    The CLI emits a single JSON object, but it may also stream NDJSON (one
    object per line). The return code is ignored on purpose -- a non-zero
    exit still often carries a usable result object -- so callers parse
    first and only fall back if nothing parses.
    """
    raw = (stdout or "").strip()
    if not raw:
        return None
    candidates = [raw]
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if len(lines) > 1:
        candidates.extend(reversed(lines))
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        text = _text_from_claude_json(data)
        if text:
            return text
    return None


def _plan_turn_llm(message: str, project_dir: str, session_id: str | None, tier1: dict, provider: str) -> dict:
    """Dispatch a planning turn.

    Provider 'cli' runs the local `claude` CLI natively with tools
    (Read,Glob,Grep), --output-format json, --add-dir, and --resume, then
    parses the JSON from stdout even when the return code is non-zero. On a
    successful parse the result is returned; on any failure or parse error a
    warning is logged and the call falls back to
    llm_client._fallback_request('cli', enriched_message, SYSTEM_PROMPT, False).

    The 'cli' fallback and every non-'cli' provider lack CLI tools, so the
    prompt is enriched first: build_context_blob() (imported from
    scripts.tier4_worker) gathers AGENTS.md, PLAN.md, and README.md from the
    project directory and the blob is prepended to the message. Non-'cli'
    providers are dispatched through llm_client.execute_llm() with the
    enriched message.

    Every successful path returns the same shape:
    {'status': 'ok', 'text': response, 'session_id': 'stateless',
     'notional_cost_usd': 0.0}.
    """
    # Enrich the prompt for paths that lack CLI tools (the 'cli' fallback and
    # every non-'cli' provider) by grounding it in the repo's own docs.
    project_path = Path(project_dir)
    context_paths = [
        fname
        for fname in ("AGENTS.md", "PLAN.md", "README.md")
        if (project_path / fname).is_file()
    ]
    context_blob = build_context_blob(context_paths, project_dir)
    enriched_message = (
        context_blob + "\n\n" + message if context_blob else message
    )

    if provider == "cli":
        cmd = [
            "claude",
            "-p", message,
            "--tools", "Read,Glob,Grep",
            "--output-format", "json",
            "--add-dir", project_dir,
        ]
        if session_id:
            cmd.extend(["--resume", session_id])

        def _fallback() -> dict:
            try:
                response_text, _billing, _in, _out = llm_client._fallback_request(
                    "cli", enriched_message, SYSTEM_PROMPT, False
                )
            except Exception as exc:
                log.error("Planning turn fallback also failed: %s", exc)
                return {"status": "error", "reason": str(exc)}
            return {
                "status": "ok",
                "text": response_text,
                "session_id": "stateless",
                "notional_cost_usd": 0.0,
            }

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
        except Exception as exc:
            log.warning("Claude CLI invocation failed: %s. Falling back.", exc)
            return _fallback()

        response_text = _extract_claude_result(result.stdout)
        if response_text:
            log.info(
                "Planning turn ok via claude CLI (returncode=%s, response_len=%d)",
                result.returncode, len(response_text),
            )
            return {
                "status": "ok",
                "text": response_text,
                "session_id": "stateless",
                "notional_cost_usd": 0.0,
            }

        log.warning(
            "Claude CLI returned no parseable JSON (returncode=%s, stderr=%s). Falling back.",
            result.returncode, (result.stderr or "")[:200],
        )
        return _fallback()

    # Non-'cli' providers: enrich and dispatch through execute_llm().
    try:
        endpoint = tier1.get("endpoint")
        api_key_secret = tier1.get("api_key_secret")
        default_key = tier1.get("default_model", "default")
        model = tier1.get("models", {}).get(default_key)
        api_key = secrets_loader.load_secrets().get(api_key_secret) if api_key_secret else None

        response_text, billing_type, in_tokens, out_tokens = llm_client.execute_llm(
            provider=provider,
            endpoint=endpoint,
            api_key=api_key,
            model=model,
            prompt=enriched_message,
            system_prompt=SYSTEM_PROMPT,
        )
    except Exception as exc:
        log.error("Planning turn failed via execute_llm (provider=%s): %s", provider, exc)
        return {"status": "error", "reason": str(exc)}

    log.info(
        "Planning turn ok: provider=%s billing=%s in_tokens=%d out_tokens=%d response_len=%d",
        provider, billing_type, in_tokens, out_tokens, len(response_text),
    )
    return {
        "status": "ok",
        "text": response_text,
        "session_id": "stateless",
        "notional_cost_usd": 0.0,
    }
