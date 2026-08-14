"""Per-model quota fallback for Gemini (Google AI Studio) calls.

Found for real 2026-08-10: Google buckets the free tier's daily request
quota PER MODEL, not per project/API-key overall -- confirmed via a live
429 body: `"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"`,
`"quotaValue": "20"` for `gemini-3.5-flash` specifically. A different model
string has its own separate, unexhausted daily allowance. Every Gemini
caller (dispatcher.py's breakdown, tier2_escalate.py's repair) should fall
through `tiers.yaml`'s `tier_2_manager.fallback_chain` in order rather than
give up (or blindly retry the same exhausted model) the moment one model's
quota is spent for the day.

Only advances on confirmed per-model quota exhaustion (429 +
RESOURCE_EXHAUSTED). Any other failure (malformed response, a different
kind of 4xx/5xx, network error) is returned as-is on the model that
produced it -- that's the caller's own retry/backoff territory, not a
reason to burn through the fallback chain.
"""

from scripts.budget_guard import record_gemini_call
from scripts.tri_logging import get_logger

log = get_logger("gemini_fallback")


def is_quota_exhausted(resp) -> bool:
    if resp.status_code != 429:
        return False
    try:
        return resp.json().get("error", {}).get("status") == "RESOURCE_EXHAUSTED"
    except ValueError:
        return False


def post_generate_content(post_fn, endpoint: str, api_key: str, body: dict, models: list[str], timeout: int):
    """Calls generateContent against each model in `models` in order,
    advancing only when the current one reports its free-tier daily quota
    exhausted. `post_fn` is `requests.post` (injected so callers/tests don't
    need to monkeypatch the module-level requests import). Returns
    (response, model_name_used) -- always the LAST response tried, whether
    that's a real success or every model in the chain was exhausted."""
    resp = None
    model = models[0]
    for model in models:
        resp = post_fn(
            f"{endpoint}/v1beta/models/{model}:generateContent",
            params={"key": api_key},
            json=body,
            timeout=timeout,
        )
        record_gemini_call(model)
        if not is_quota_exhausted(resp):
            return resp, model
        log.warning("Gemini model %s: free-tier daily quota exhausted, falling back to next model", model)
    return resp, model
