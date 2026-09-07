"""Sanitizes text bound for OpenRouter's content filter.

OpenRouter's content filter can 403 a request whose prompt contains an
email/phone/IP-shaped token, even a synthetic one in test/task fixture
data -- ported from the old pipeline's scripts/llm_client.py (real live
blocks there, 2026-08-24/25: 36 blocked requests in one day -- 18 PHONE,
12 EMAIL, 6 IP ADDRESS). Used by llm_client.execute_openrouter, the
fallback's single call site.
"""

import re

_EMAIL_LIKE_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")

# NANP-style phone shape (3-3-4 digit groups with separators). Anchored to
# that exact grouping so it does NOT match run-id timestamps ("20260824-
# 153000-a1b2c3"), hex hashes, or version strings ("1.2.3") -- see
# rebuild/tests/test_openrouter_sanitizer.py's false-positive cases, ported
# from the old pipeline's tests/test_llm_client_sanitize.py.
_PHONE_LIKE_RE = re.compile(
    r"\b(?:\+\d{1,3}\s*)?(?:\(\d{3}\)\s*|\d{3}[\s.\-])\d{3}[\s.\-]\d{4}\b"
)

# IPv4-shaped tokens (four dot-separated octets).
_IP_LIKE_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\b"
)


def _redact_phone_like(match: re.Match) -> str:
    return re.sub(r"[\s.\-()]", "-REDACTED-", match.group(0))


def _redact_ip_like(match: re.Match) -> str:
    return match.group(0).replace(".", "-REDACTED-")


def sanitize_for_openrouter_content_filter(text: str) -> str:
    text = _EMAIL_LIKE_RE.sub(lambda m: m.group(0).replace("@", "(at)"), text)
    text = _PHONE_LIKE_RE.sub(_redact_phone_like, text)
    text = _IP_LIKE_RE.sub(_redact_ip_like, text)
    return text
