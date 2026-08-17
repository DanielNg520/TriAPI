"""Jules (Google's async coding-agent) REST API client.

Thin wrapper around the Jules API (`jules.googleapis.com`) mirroring
tier2_escalate.py's module shape: module-level constants, small pure
request-building/parsing helpers, and a poll loop. Used to hand off a task
to Jules as an out-of-band tier and later collect its result.

Auth is a plain API key header (`X-Goog-Api-Key`), loaded via
secrets_loader.load_secrets()["google_jules_apikey"] -- never logged.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.secrets_loader import load_secrets
from scripts.tri_logging import get_logger

log = get_logger("jules")

BASE_URL = "https://jules.googleapis.com/v1alpha"

# Session states considered terminal -- polling stops on any of these.
TERMINAL_STATES = {"COMPLETED", "FAILED", "CANCELLED"}

DEFAULT_POLL_INTERVAL_SECONDS = 15
DEFAULT_POLL_TIMEOUT_SECONDS = 1800


def _headers(api_key: str) -> dict:
    return {
        "X-Goog-Api-Key": api_key,
        "Content-Type": "application/json",
    }


def create_session(
    prompt: str,
    source: str,
    api_key: str,
    title: str = "",
    starting_branch: str = "main",
    require_plan_approval: bool = False,
    timeout: int = 60,
) -> dict:
    """Create a new Jules session against a GitHub source.

    `source` is the Jules source resource name, e.g. "sources/github/owner/repo".
    Returns the created Session resource (dict) as parsed JSON.
    Raises requests.RequestException / requests.HTTPError on transport or
    non-2xx failures -- callers are expected to handle these the same way
    tier2_escalate.py handles Gemini request failures.
    """
    payload = {
        "prompt": prompt,
        "sourceContext": {
            "source": source,
            "githubRepoContext": {
                "startingBranch": starting_branch,
            },
        },
        "requirePlanApproval": require_plan_approval,
    }
    if title:
        payload["title"] = title

    resp = requests.post(
        f"{BASE_URL}/sessions",
        headers=_headers(api_key),
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def get_session_state(session_name: str, api_key: str, timeout: int = 30) -> dict:
    """Fetch the current Session resource (dict) for `session_name`.

    `session_name` is the resource name returned by create_session, e.g.
    "sessions/abc123" -- not a bare ID.
    """
    resp = requests.get(
        f"{BASE_URL}/{session_name}",
        headers=_headers(api_key),
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def get_final_message(session_name: str, api_key: str, timeout: int = 30) -> str | None:
    """Return the text of the last agent-authored message in the session's
    activity feed, or None if no agent message is present.
    """
    resp = requests.get(
        f"{BASE_URL}/{session_name}/activities",
        headers=_headers(api_key),
        params={"pageSize": 100},
        timeout=timeout,
    )
    resp.raise_for_status()
    activities = resp.json().get("activities", [])

    final_message = None
    for activity in activities:
        agent_messaged = activity.get("agentMessaged")
        if agent_messaged and agent_messaged.get("agentMessage"):
            final_message = agent_messaged["agentMessage"]
    return final_message


def poll_session_result(
    session_name: str,
    api_key: str,
    poll_interval: int = DEFAULT_POLL_INTERVAL_SECONDS,
    timeout: int = DEFAULT_POLL_TIMEOUT_SECONDS,
) -> dict:
    """Poll a Jules session until it reaches a terminal state or `timeout`
    (seconds, wall-clock) elapses.

    Returns a dict:
        {"status": "completed", "state": ..., "final_message": ..., "session": ...}
        {"status": "failed", "state": ..., "final_message": ..., "session": ...}
        {"status": "cancelled", "state": ..., "final_message": ..., "session": ...}
        {"status": "timeout", "state": <last observed state>, "session": <last observed>}
        {"status": "error", "reason": <str>}
    Never raises -- transport/HTTP errors during polling are caught and
    returned as an "error" result, matching tier2_escalate.py's pattern of
    never letting a tier crash the unattended dispatch process.
    """
    deadline = time.monotonic() + timeout
    last_session: dict = {}

    while True:
        try:
            session = get_session_state(session_name, api_key)
        except requests.RequestException as e:
            log.error("Jules poll failed for %s: %s", session_name, e)
            return {"status": "error", "reason": f"Jules poll failed: {e}"}

        last_session = session
        state = session.get("state", "")
        log.info("Jules session %s state=%s", session_name, state)

        if state in TERMINAL_STATES:
            try:
                final_message = get_final_message(session_name, api_key)
            except requests.RequestException as e:
                log.warning(
                    "Jules session %s reached terminal state %s but fetching "
                    "final message failed: %s", session_name, state, e,
                )
                final_message = None

            status = {
                "COMPLETED": "completed",
                "FAILED": "failed",
                "CANCELLED": "cancelled",
            }[state]
            return {
                "status": status,
                "state": state,
                "final_message": final_message,
                "session": session,
            }

        if time.monotonic() >= deadline:
            log.warning(
                "Jules session %s did not reach a terminal state within %ss "
                "(last state=%s)", session_name, timeout, state,
            )
            return {"status": "timeout", "state": state, "session": last_session}

        time.sleep(poll_interval)


def run_jules_test(
    prompt: str,
    source: str,
    title: str = "TriAPI Jules smoke test",
    starting_branch: str = "main",
    poll_interval: int = DEFAULT_POLL_INTERVAL_SECONDS,
    timeout: int = DEFAULT_POLL_TIMEOUT_SECONDS,
) -> dict:
    """End-to-end: create a session, poll it to completion, and return the
    poll result. Used both by `triapi.py`'s post-dispatch advisory hook and
    by `main()` for a manual/CLI smoke test of Jules API credentials and
    connectivity.
    """
    try:
        secrets = load_secrets()
    except (FileNotFoundError, RuntimeError, ValueError) as e:
        log.error("Jules test: could not load secrets: %s", e)
        return {"status": "error", "reason": f"Could not load secrets: {e}"}

    api_key = secrets.get("google_jules_apikey")
    if not api_key:
        log.error("Jules test: 'google_jules_apikey' missing from secrets")
        return {"status": "error", "reason": "'google_jules_apikey' missing from secrets"}

    try:
        session = create_session(
            prompt=prompt,
            source=source,
            api_key=api_key,
            title=title,
            starting_branch=starting_branch,
        )
    except requests.RequestException as e:
        log.error("Jules test: create_session failed: %s", e)
        return {"status": "error", "reason": f"create_session failed: {e}"}

    session_name = session.get("name")
    if not session_name:
        log.error("Jules test: create_session response missing 'name': %s", session)
        return {"status": "error", "reason": "create_session response missing 'name'"}

    log.info("Jules test: created session %s", session_name)

    return poll_session_result(
        session_name,
        api_key,
        poll_interval=poll_interval,
        timeout=timeout,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True, help="task prompt to send to Jules")
    parser.add_argument(
        "--source", required=True,
        help="Jules source resource name, e.g. sources/github/owner/repo",
    )
    parser.add_argument("--title", default="TriAPI Jules smoke test")
    parser.add_argument("--starting-branch", default="main")
    parser.add_argument("--poll-interval", type=int, default=DEFAULT_POLL_INTERVAL_SECONDS)
    parser.add_argument("--timeout", type=int, default=DEFAULT_POLL_TIMEOUT_SECONDS)
    args = parser.parse_args()

    result = run_jules_test(
        prompt=args.prompt,
        source=args.source,
        title=args.title,
        starting_branch=args.starting_branch,
        poll_interval=args.poll_interval,
        timeout=args.timeout,
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
