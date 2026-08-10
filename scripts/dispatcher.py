"""Tier 2 (as Manager): breaks a Tier-1 plan into phases of concrete
checklist items -- one file + one task each -- then dispatches them to the
existing repair pipeline (orchestrator.run_task()) one at a time, in order.

Distinct from tier2_escalate.py, which uses the Gemini API as a repair
tier for a single already-known-broken file. This module uses Gemini in
the manager role from the original design: turning a rough plan into a
strict, executable checklist and working through it sequentially.

Run state is persisted to logs/runs/<run_id>.json after every single item
completes (not just at the end), so a long-running plan survives an SSH
disconnect -- resume by re-reading the same run_id.

Must only be called after budget_guard.check_tier2_ok().
"""

import json
import shlex
import time
import uuid
from pathlib import Path

import requests

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import git_ops
from scripts.budget_guard import check_tier2_ok, record_gemini_call
from scripts.config_loader import load_tiers
from scripts.orchestrator import human_handoff, run_task, verify_task
from scripts.secrets_loader import load_secrets
from scripts.tri_logging import get_logger

log = get_logger("dispatcher")

RUNS_DIR = Path(__file__).resolve().parent.parent / "logs" / "runs"

BREAKDOWN_SYSTEM_INSTRUCTION = (
    "You manage a team of coding workers. Given ONE PHASE of an execution plan "
    "(markdown, a single phase containing a checklist of steps), convert it "
    "into strict JSON with this exact shape: "
    '{"name": "the phase name", "items": [ITEM, ...]}. '
    "If a single checklist bullet names multiple files to edit, split it into "
    "one ITEM per file -- never combine multiple files into one item's "
    "'target'. Each ITEM is one of two shapes:\n"
    "1. A file item: "
    '{"description": "...", "target": "relative/path/to/file", "build_cmd": "shell command to build/verify", "verify_only": false}. '
    "One item per file that needs creating or changing. Set 'verify_only': "
    "true when the step is a pure check with NO file content to draft/change "
    "-- e.g. \"run the test suite\", \"grep for no remaining call sites\", "
    "\"confirm output looks like X\". For those, 'target' should name the "
    "most relevant existing file (e.g. the test runner, or one of the dormant "
    "files being checked for stray references) but it will NOT be drafted or "
    "overwritten -- only 'build_cmd' actually runs. Getting 'verify_only' "
    "wrong on a step that has nothing to write is dangerous: it would cause "
    "an AI worker to overwrite a file (like a test runner script) that was "
    "never supposed to change at all. Default false only for steps that "
    "genuinely create or edit that file's content.\n"
    "2. A git item, ONLY for an explicit git clone/pull/push step named in the "
    "plan (do not invent git steps that aren't in the plan): "
    '{"description": "...", "git": {"action": "clone", "url": "...", "path": "relative/or/absolute/path"}} or '
    '{"description": "...", "git": {"action": "pull", "path": "relative/or/absolute/path"}} or '
    '{"description": "...", "git": {"action": "push", "path": "relative/or/absolute/path", "message": "commit message", "branch": "optional, only if the plan names a specific branch"}}.\n'
    "'path' is REQUIRED on every git action once a repo directory is known -- "
    "it's the directory the git command runs in. For 'clone' it's where the new "
    "clone goes (relative to the project directory). For 'pull'/'push' it MUST "
    "be the actual repo directory, which is very often NOT the project's top "
    "level -- e.g. if an earlier clone step's path was 'repo', every later "
    "pull/push step operating on that clone must also use path 'repo', not omit "
    "it. Getting this wrong makes the command run in a directory with no git "
    "repo at all, which fails immediately.\n"
    "Preserve this phase's step order exactly, do not reorder or merge steps "
    "into each other (except splitting a multi-file bullet into one item per "
    "file, as above). Each 'description' is the ONLY context the worker doing "
    "this step will see -- it will NOT see the original plan or phase text. "
    "Carry forward every concrete technical requirement from that step "
    "verbatim: language/standard version, exact expected output/behavior, "
    "library versions, interfaces, anything specific. Summarizing away a "
    "specific requirement (e.g. dropping 'C++17' down to just 'create the "
    "file') is a failure, not a simplification. A step with no single file to "
    "create/change (e.g. \"run the test suite\", \"grep for X\") is still a "
    "file item -- use the most relevant existing file as 'target' (e.g. the "
    "repo root config/test file) and put the actual check in 'build_cmd'. "
    "Output ONLY the JSON for this one phase, no explanation, no markdown "
    "code fence, and do NOT wrap it in a 'phases' list -- just the single "
    "{\"name\": ..., \"items\": [...]} object."
)


def _split_plan_by_phase(plan_text: str) -> list[str]:
    """Splits plan markdown into chunks on '## ' headers (one chunk per
    phase, keeping its header), so each phase can be broken down into JSON
    independently. Asking Gemini for the WHOLE plan's JSON in one call fails
    on large plans -- observed: malformed/truncated JSON past ~500 lines of
    output for a real 9-phase plan. Smallest reliable batch, not fewer,
    bigger calls."""
    lines = plan_text.splitlines(keepends=True)
    chunks = []
    current = []
    for line in lines:
        if line.startswith("## ") and current:
            chunks.append("".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        chunks.append("".join(current))
    # Drop chunks with no checklist items (e.g. a leading title/context
    # block before the first '## ' header) -- nothing to break down.
    return [c for c in chunks if "- [ ]" in c]


def _breakdown_phase_attempt(phase_text: str, model_name: str, tier2: dict, secrets: dict) -> dict:
    resp = requests.post(
        f"{tier2['endpoint']}/v1beta/models/{model_name}:generateContent",
        params={"key": secrets["google_ai_studio_api_key"]},
        json={
            "systemInstruction": {"parts": [{"text": BREAKDOWN_SYSTEM_INSTRUCTION}]},
            "contents": [{"role": "user", "parts": [{"text": phase_text}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        },
        timeout=120,
    )
    record_gemini_call()
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        log.error("Phase breakdown request failed: %s %s", resp.status_code, resp.text[:500])
        raise
    data = resp.json()

    text = data["candidates"][0]["content"]["parts"][0]["text"]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        log.error("Phase breakdown returned invalid JSON: %s", e)
        return {"status": "error", "reason": f"Gemini did not return valid JSON for this phase: {e}"}

    if "name" not in parsed or "items" not in parsed or not isinstance(parsed["items"], list):
        log.error("Phase breakdown JSON missing 'name'/'items': %s", text[:500])
        return {"status": "error", "reason": "phase breakdown JSON missing 'name'/'items'"}

    return {"status": "ok", "phase": parsed}


def breakdown_phase(phase_text: str, model: str | None = None, max_attempts: int = 3) -> dict:
    """Breaks down ONE phase's markdown into {"name", "items"}. See
    _split_plan_by_phase for why this is per-phase, not per-plan.

    Retries on malformed JSON: Gemini's responseMimeType=application/json
    mode is not 100% reliable even for small, simple inputs -- observed the
    exact same tiny (307-char) phase produce valid JSON on one call and
    malformed JSON on the next, with no input change. This is a transient/
    stochastic failure, not a deterministic bug, so retrying is the right
    response -- time is not a constraint here, a wrong plan running is what
    actually costs something."""
    guard = check_tier2_ok()
    if not guard["ok"]:
        log.warning("Phase breakdown skipped: %s", guard["reason"])
        return {"status": "skipped", "reason": guard["reason"]}

    config = load_tiers()
    tier2 = config["tier_2_manager"]
    secrets = load_secrets()
    model_name = model or tier2["models"][tier2["default_model"]]

    log.info("Requesting phase breakdown from Gemini/%s (%d chars)", model_name, len(phase_text))

    last_result = None
    for attempt in range(1, max_attempts + 1):
        result = _breakdown_phase_attempt(phase_text, model_name, tier2, secrets)
        if result["status"] == "ok":
            log.info("Phase breakdown ok (attempt %d/%d): %r, %d item(s)", attempt, max_attempts, result["phase"]["name"], len(result["phase"]["items"]))
            return result
        log.warning("Phase breakdown attempt %d/%d failed: %s", attempt, max_attempts, result.get("reason"))
        last_result = result

    return last_result


def breakdown_plan(state: dict) -> dict:
    """Breaks state['plan_text'] down phase by phase, saving state after
    each phase succeeds -- resumable, and each individual Gemini call stays
    small and reliable. Skips phases already present in
    state['breakdown']['phases'] (so re-entering a partially-broken-down
    run doesn't redo completed phases)."""
    if state["breakdown"] is None:
        state["breakdown"] = {"phases": []}
        save_run(state)

    chunks = _split_plan_by_phase(state["plan_text"])
    already_done = len(state["breakdown"]["phases"])

    for i, chunk in enumerate(chunks):
        if i < already_done:
            continue
        result = breakdown_phase(chunk)
        if result["status"] != "ok":
            return result
        state["breakdown"]["phases"].append(result["phase"])
        save_run(state)
        print(
            f"  Broken down phase {i + 1}/{len(chunks)}: "
            f"{result['phase']['name']} ({len(result['phase']['items'])} item(s))"
        )

    total_items = sum(len(p["items"]) for p in state["breakdown"]["phases"])
    log.info("Breakdown ok: %d phase(s), %d item(s) total", len(state["breakdown"]["phases"]), total_items)
    return {"status": "ok"}


def _run_path(run_id: str) -> Path:
    return RUNS_DIR / f"{run_id}.json"


def save_run(state: dict) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = time.time()
    with open(_run_path(state["run_id"]), "w") as f:
        json.dump(state, f, indent=2)


def load_run(run_id: str) -> dict:
    with open(_run_path(run_id)) as f:
        return json.load(f)


def list_runs() -> list[dict]:
    if not RUNS_DIR.exists():
        return []
    runs = []
    for path in sorted(RUNS_DIR.glob("*.json")):
        try:
            with open(path) as f:
                state = json.load(f)
            runs.append(
                {
                    "run_id": state["run_id"],
                    "status": state["status"],
                    "prompt": state["prompt"],
                    "started_at": state["started_at"],
                }
            )
        except (json.JSONDecodeError, KeyError):
            continue
    return runs


def new_run(prompt: str, project_dir: str) -> dict:
    run_id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    state = {
        "run_id": run_id,
        "prompt": prompt,
        "project_dir": str(Path(project_dir).resolve()),
        "status": "planning",
        "plan_text": None,
        "breakdown": None,
        "results": [],
        "started_at": time.time(),
    }
    save_run(state)
    return state


def _resolve_path(path_str: str, project_dir: str) -> str:
    p = Path(path_str)
    return str(p if p.is_absolute() else Path(project_dir) / p)


def _dispatch_git_item(task_id: str, git_spec: dict, project_dir: str) -> dict:
    action = git_spec.get("action")
    path = _resolve_path(git_spec.get("path", "."), project_dir)
    log.info("[%s] Git action: %s (path=%s)", task_id, action, path)

    if action == "clone":
        result = git_ops.clone(git_spec["url"], path)
    elif action == "pull":
        result = git_ops.pull(path)
    elif action == "push":
        result = git_ops.push(
            path,
            message=git_spec.get("message", f"TriAPI: {task_id}"),
            branch=git_spec.get("branch"),
        )
    else:
        result = {"ok": False, "output": f"unknown git action: {action!r}"}

    if result["ok"]:
        return {"status": "success", "resolved_by": "git"}

    human_handoff(task_id, f"git {action} failed", f"**Output:**\n```\n{result['output']}\n```")
    return {"status": "human_handoff", "resolved_by": None}


def dispatch(state: dict) -> dict:
    """Walks state['breakdown']['phases'] sequentially, one item at a time,
    resuming from wherever state['results'] left off (so re-entering an
    already-partially-dispatched run doesn't redo completed items)."""
    phases = state["breakdown"]["phases"]
    state["status"] = "dispatching"

    # We always stop immediately on the first non-success item, so at most
    # one trailing result can be non-success -- drop it so it gets retried
    # rather than being treated as permanently done.
    if state["results"] and state["results"][-1]["status"] != "success":
        retried = state["results"].pop()
        log.info("[%s] Retrying previously-failed item %s on resume", state["run_id"], retried["task_id"])

    save_run(state)
    log.info("[%s] Dispatch starting (%d already-completed item(s) to skip)", state["run_id"], len(state["results"]))

    already_done = len(state["results"])
    seen = 0
    for pi, phase in enumerate(phases):
        for ii, item in enumerate(phase["items"]):
            if seen < already_done:
                seen += 1
                continue
            task_id = f"{state['run_id']}-p{pi}-i{ii}"
            print(f"[{phase['name']}] ({ii + 1}/{len(phase['items'])}) {item['description']}")

            if "git" in item:
                result = _dispatch_git_item(task_id, item["git"], state["project_dir"])
            elif item.get("verify_only"):
                # Nothing to draft/change -- run the check as-is, never let
                # an AI tier overwrite a file (e.g. a test runner script)
                # that was never supposed to change.
                if not item.get("build_cmd"):
                    result = {"status": "human_handoff", "resolved_by": None}
                    human_handoff(task_id, "verify_only item has no build_cmd to run", item["description"])
                else:
                    result = verify_task(task_id, item["build_cmd"], workdir=state["project_dir"])
            else:
                # An empty build_cmd means Gemini judged this item has nothing
                # to build (e.g. documentation) -- verify by existence, not by
                # falling through to orchestrator's default cmake build, which
                # is nonsensical for a non-code file and would fail forever.
                build_cmd = item.get("build_cmd") or f"test -f {shlex.quote(item['target'])}"

                result = run_task(
                    task_id=task_id,
                    description=item["description"],
                    target=item["target"],
                    workdir=state["project_dir"],
                    build_cmd=build_cmd,
                )
            state["results"].append(
                {
                    "task_id": task_id,
                    "phase": phase["name"],
                    "item": item["description"],
                    "status": result["status"],
                    "resolved_by": result["resolved_by"],
                }
            )
            save_run(state)
            print(f"  -> {result['status']} (resolved_by={result['resolved_by']})")
            log.info("[%s] Item %s: %s (resolved_by=%s)", state["run_id"], task_id, result["status"], result["resolved_by"])

            if result["status"] != "success":
                log.warning("[%s] Dispatch stopping: item %s did not resolve", state["run_id"], task_id)
                state["status"] = "stopped_on_failure"
                save_run(state)
                return state

    log.info("[%s] Dispatch completed: all items resolved", state["run_id"])
    state["status"] = "completed"
    save_run(state)
    return state
