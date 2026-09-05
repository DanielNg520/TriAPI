"""Phase breakdown logic for the Tier 2 dispatcher."""

import json
import re
import time

# BREAKDOWN_SYSTEM_INSTRUCTION itself lives in breakdown_prompts.py (split
# out 2026-08-28 to stay under this repo's file-size ceiling); re-exported
# here so existing callers/tests referencing dispatcher.BREAKDOWN_SYSTEM_INSTRUCTION
# keep working unchanged.
from scripts.breakdown_prompts import BREAKDOWN_SYSTEM_INSTRUCTION
from scripts.budget_guard import check_tier2_ok, resolve_peak_conditional
from scripts.config_loader import load_tiers
from scripts.llm_client import execute_llm
from scripts.secrets_loader import load_secrets
from scripts.tri_logging import get_logger

log = get_logger("dispatcher")

# Path-like references in item description text; used as deterministic context_files fallback.
_FILE_REF_RE = re.compile(
    r"[\w][\w-]*(?:/[\w.-]+)+\.\w+"
    r"|\b[\w-]+\.(?:py|md|yaml|yml|json|js|ts|jsx|tsx|toml|cfg|ini|sh|txt)\b"
)

# Duplicated from dispatcher.py (not imported) to avoid a circular import:
# dispatcher.py imports breakdown_phase from this module, so this module
# can't import back from dispatcher.py at module load time. dispatcher.py's
# own _CHECKLIST_ITEM_RE (used by _split_plan_by_phase) stays the source of
# truth there; this is only used internally by _split_phase_by_dense_bullet.
_CHECKLIST_ITEM_RE = re.compile(r"^\s*(?:[-*]|\d+\.)\s+", re.MULTILINE)


def _backstop_context_files(item: dict) -> None:
    """Extract referenced paths from the item description into context_files as a deterministic fallback."""
    target = item.get("target")
    referenced = [p for p in _FILE_REF_RE.findall(item.get("description", "")) if p != target]
    if not referenced:
        return
    existing = item.get("context_files") or []
    merged = list(existing)
    for p in referenced:
        if p not in merged:
            merged.append(p)
    if merged != existing:
        item["context_files"] = merged


def _breakdown_phase_attempt(phase_text: str, models: list[str], tier2: dict, secrets: dict) -> dict:
    # 2026-09-01: always the generic execute_llm path now, for every
    # provider -- the special-cased "google" branch (gemini_fallback.py's
    # per-model quota fallback) was removed once the account moved off
    # Google AI Studio's free tier, where that quota limit applied.
    provider = tier2.get("provider", "openrouter")

    from scripts.llm_client import execute_llm
    try:
        api_key = secrets.get(tier2.get("api_key_secret", "open_router_api_key"))
        text, _, _, _ = execute_llm(
            provider=provider,
            # .get(), not tier2["endpoint"] -- an agy-provider block (e.g.
            # tier_2_manager's peak_alt, resolved by resolve_peak_conditional()
            # above during DeepSeek's peak billing window) has no "endpoint"
            # key at all, same as every other agy call site in this repo
            # (tier2_escalate.py, tier3_escalate.py both already use .get()
            # here). A strict subscript crashed with KeyError: 'endpoint'
            # the first time a real breakdown ran during peak hours -- found
            # live 2026-09-02.
            endpoint=tier2.get("endpoint"),
            api_key=api_key,
            model=models[0],
            prompt=phase_text,
            system_prompt=BREAKDOWN_SYSTEM_INSTRUCTION,
            # tier2.get("effort"), not omitted -- an agy-provider block
            # (e.g. tier_2_manager's peak_alt, effort: high in
            # config/tiers.yaml) is rejected by the live `agy` CLI with
            # "--model gemini-3.1-pro requires --effort" when no effort is
            # passed at all. Every other real agy call site in this repo
            # (tier2_escalate.py, tier3_escalate.py) already threads this
            # through; this one didn't. Found live 2026-09-02, right after
            # the endpoint KeyError above was fixed -- exit status 1 with no
            # stderr surfaced in the logged exception message (see
            # _call_agy_cli's non-JSON-decode CalledProcessError branch,
            # which doesn't embed stderr like its sibling branches do).
            effort=tier2.get("effort"),
        )
    except Exception as e:
        log.error("Phase breakdown request failed: %s", e)
        return {"status": "error", "reason": f"LLM request failed: {e}", "retry_after": None}

    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        log.error("Phase breakdown returned invalid JSON: %s", e)
        return {"status": "error", "reason": f"Gemini did not return valid JSON for this phase: {e}"}

    if "name" not in parsed or "items" not in parsed or not isinstance(parsed["items"], list):
        log.error("Phase breakdown JSON missing 'name'/'items': %s", text[:500])
        return {"status": "error", "reason": "phase breakdown JSON missing 'name'/'items'"}

    for item in parsed["items"]:
        if "git" in item:
            continue
        _backstop_context_files(item)

    return {"status": "ok", "phase": parsed}


# Top-level checklist bullet: no leading indentation, unlike a bullet's own
# wrapped continuation lines or nested sub-bullets. Deliberately narrower
# than _CHECKLIST_ITEM_RE (which allows any indentation) -- this is used to
# find bullet BOUNDARIES within a phase, where an indented match would
# wrongly split a bullet's own body away from its marker line.
_TOP_LEVEL_BULLET_RE = re.compile(r"^(?:[-*]|\d+\.)\s+")

# Chars: a real incident (2026-09-01/02) showed a single unusually long/
# dense checklist bullet losing most of its technical detail during Tier 2
# phase-breakdown compression, despite BREAKDOWN_SYSTEM_INSTRUCTION's
# explicit "carry forward every concrete technical requirement... failure
# to do so" instruction -- the instruction alone isn't enough once one call
# has to compress many bullets at once including one much longer than the
# rest. No principled threshold exists; this is a conservative starting
# point (well above a normal single-file bullet, which is usually under
# 1,000 chars in practice).
_DENSE_BULLET_THRESHOLD = 4000


def _split_phase_by_dense_bullet(phase_text: str, threshold: int = _DENSE_BULLET_THRESHOLD) -> tuple[str, str] | None:
    """If phase_text has a single top-level checklist bullet whose own text
    clearly dominates the phase (>= threshold chars AND >= half of all
    bullet text combined), split it out so a later breakdown_phase() call
    gives it undivided attention instead of competing for compression
    budget against every other bullet in the same Gemini call.

    Returns None when no split is warranted (nothing to split against, or
    no single bullet dominates -- several long-ish bullets of similar size
    are left alone, since there's no one bullet to isolate). Otherwise
    returns (rest_text, dense_text): two standalone phase-shaped chunks,
    each keeping the phase's own header line so both stay independently
    breakdownable -- rest_text has the dense bullet excised, dense_text is
    the header plus the dense bullet alone."""
    lines = phase_text.splitlines(keepends=True)
    bullet_starts = [i for i, line in enumerate(lines) if _TOP_LEVEL_BULLET_RE.match(line)]
    if len(bullet_starts) < 2:
        return None
    header = "".join(lines[:bullet_starts[0]])
    bullets = [
        "".join(lines[start:(bullet_starts[idx + 1] if idx + 1 < len(bullet_starts) else len(lines))])
        for idx, start in enumerate(bullet_starts)
    ]
    lengths = [len(b) for b in bullets]
    max_idx = max(range(len(lengths)), key=lengths.__getitem__)
    max_len = lengths[max_idx]
    if max_len < threshold or max_len < sum(lengths) / 2:
        return None
    dense_text = header + bullets[max_idx]
    rest_text = header + "".join(b for i, b in enumerate(bullets) if i != max_idx)
    if not _CHECKLIST_ITEM_RE.search(rest_text):
        return None  # the dense bullet was the only bullet -- nothing to split off
    return rest_text, dense_text


def breakdown_phase(phase_text: str, model: str | None = None, max_attempts: int = 3, _dense_split_depth: int = 0) -> dict:
    """Breaks down ONE phase's markdown into {"name", "items"}. See
    _split_plan_by_phase for why this is per-phase, not per-plan.

    Retries on malformed JSON: Gemini's responseMimeType=application/json
    mode is not 100% reliable even for small, simple inputs -- the exact
    same tiny (307-char) phase produced valid JSON on one call and
    malformed JSON on the next, with no input change. Transient/stochastic,
    not deterministic, so retrying is right -- time isn't a constraint
    here, a wrong plan running is what actually costs something.

    An RPM refusal from check_tier2_ok() is retried the same way (the
    sliding window empties within 60s) -- found live 2026-08-12: a large
    plan's per-phase Gemini calls easily burst past a 10 RPM cap, and the
    previous immediate "skipped" return killed the whole breakdown (marking
    the run "failed" instead of resumable) over a condition that clears in
    under a minute. An RPD refusal is NOT retried -- it won't clear until
    the next day, so this case still returns immediately.

    If one checklist bullet clearly dominates this phase's size, it's
    split off (_split_phase_by_dense_bullet) and broken down in its own
    recursive call so it isn't compressed alongside the rest -- see that
    function's docstring for the incident this fixes. `_dense_split_depth`
    is internal (bounds the recursion so unusual markdown, e.g. an
    unindented dash line inside the dense bullet's own body, can't loop
    indefinitely) and isn't meant to be passed by callers."""
    if _dense_split_depth < 3:
        split = _split_phase_by_dense_bullet(phase_text)
        if split is not None:
            rest_text, dense_text = split
            log.info(
                "Phase breakdown: splitting off one dense bullet (%d chars) from the rest (%d chars) for separate breakdown calls",
                len(dense_text), len(rest_text),
            )
            rest_result = breakdown_phase(rest_text, model=model, max_attempts=max_attempts, _dense_split_depth=_dense_split_depth + 1)
            if rest_result["status"] != "ok":
                return rest_result
            dense_result = breakdown_phase(dense_text, model=model, max_attempts=max_attempts, _dense_split_depth=_dense_split_depth + 1)
            if dense_result["status"] != "ok":
                return dense_result
            return {
                "status": "ok",
                "phase": {
                    "name": rest_result["phase"]["name"] or dense_result["phase"]["name"],
                    "items": rest_result["phase"]["items"] + dense_result["phase"]["items"],
                },
            }

    config = load_tiers()
    # Resolve peak_alt like every other real Tier 2 call site (e.g.
    # tier2_escalate.py) does -- without this, phase-breakdown calls kept
    # hitting DeepSeek's raw off-peak config even during its peak billing
    # window, instead of promoting to the configured peak_alt provider.
    tier2 = resolve_peak_conditional(config["tier_2_manager"])
    secrets = load_secrets()
    default_model = tier2["models"][tier2["default_model"]]
    # An explicit model override is honored exactly, no fallback -- the
    # caller asked for that one specifically. Otherwise walk the configured
    # chain (Phase 14: per-model daily quota fallback) so one exhausted
    # model doesn't stall the whole breakdown.
    models = [model] if model else (tier2.get("fallback_chain") or [default_model])

    log.info("Requesting phase breakdown from Gemini/%s (%d chars)", models[0], len(phase_text))

    last_result = None
    for attempt in range(1, max_attempts + 1):
        guard = check_tier2_ok()
        if not guard["ok"]:
            if "RPD" in guard["reason"]:
                # Daily quota -- won't clear during this run, don't busy-wait.
                log.warning("Phase breakdown skipped: %s", guard["reason"])
                return {"status": "skipped", "reason": guard["reason"]}
            result = {"status": "error", "reason": guard["reason"], "retry_after": 65.0}
        else:
            result = _breakdown_phase_attempt(phase_text, models, tier2, secrets)

        if result["status"] == "ok":
            log.info("Phase breakdown ok (attempt %d/%d): %r, %d item(s)", attempt, max_attempts, result["phase"]["name"], len(result["phase"]["items"]))
            return result
        log.warning("Phase breakdown attempt %d/%d failed: %s", attempt, max_attempts, result.get("reason"))
        last_result = result

        if attempt < max_attempts:
            # Retrying instantly against a rate limit just 429s again --
            # observed for real: 3 attempts fired within ~300ms of each
            # other, all rejected. Honor the server's own backoff hint when
            # given (Google's 429 body names an exact delay); otherwise a
            # short fixed pause covers the malformed-JSON case, which is
            # genuinely transient/stochastic, not rate-limited.
            delay = result.get("retry_after") or 5.0
            log.info("Backing off %.1fs before retry %d/%d", delay, attempt + 1, max_attempts)
            time.sleep(delay)

    return last_result
