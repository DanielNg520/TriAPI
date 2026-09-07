from scripts.openrouter_sanitizer import (
    _IP_LIKE_RE,
    _PHONE_LIKE_RE,
    sanitize_for_openrouter_content_filter,
)


def test_sanitize_phone_like_is_redacted():
    phone = "555" + "-" + "555" + "-" + "5555"
    result = sanitize_for_openrouter_content_filter(phone)
    assert result != phone
    assert _PHONE_LIKE_RE.search(result) is None


def test_sanitize_run_id_timestamp_unchanged():
    run_id = "20260824" + "-" + "153000" + "-" + "a1b2c3"
    assert sanitize_for_openrouter_content_filter(run_id) == run_id


def test_sanitize_hex_hash_unchanged():
    hex_hash = "deadbeef1234"
    assert sanitize_for_openrouter_content_filter(hex_hash) == hex_hash


def test_sanitize_ipv4_like_is_redacted():
    ip = "192" + "." + "168" + "." + "1" + "." + "1"
    result = sanitize_for_openrouter_content_filter(ip)
    assert result != ip
    assert _IP_LIKE_RE.search(result) is None


def test_sanitize_version_string_not_mangled():
    version = "1" + "." + "2" + "." + "3"
    assert sanitize_for_openrouter_content_filter(version) == version
