"""Tests for _sanitize_for_openrouter_content_filter phone and IP cases."""

import re
import unittest

from scripts.llm_client import (
    _sanitize_for_openrouter_content_filter,
    _PHONE_LIKE_RE,
    _IP_LIKE_RE,
)


class SanitizePhoneTests(unittest.TestCase):
    def test_phone_like_is_redacted(self):
        # Build at runtime to avoid literal real-looking string in source.
        phone = "555" + "-" + "555" + "-" + "5555"
        result = _sanitize_for_openrouter_content_filter(phone)
        self.assertNotEqual(result, phone)
        # Original 3-3-4 grouping must no longer match the phone regex.
        self.assertIsNone(_PHONE_LIKE_RE.search(result))

    def test_run_id_timestamp_unchanged(self):
        run_id = "20260824" + "-" + "153000" + "-" + "a1b2c3"
        result = _sanitize_for_openrouter_content_filter(run_id)
        self.assertEqual(result, run_id)

    def test_hex_hash_unchanged(self):
        hex_hash = "deadbeef1234"
        result = _sanitize_for_openrouter_content_filter(hex_hash)
        self.assertEqual(result, hex_hash)


class SanitizeIPTests(unittest.TestCase):
    def test_ipv4_like_is_redacted(self):
        ip = "192" + "." + "168" + "." + "1" + "." + "1"
        result = _sanitize_for_openrouter_content_filter(ip)
        self.assertNotEqual(result, ip)
        # Original dotted-quad must no longer match the IP regex.
        self.assertIsNone(_IP_LIKE_RE.search(result))

    def test_version_string_not_mangled(self):
        version = "1" + "." + "2" + "." + "3"
        result = _sanitize_for_openrouter_content_filter(version)
        self.assertEqual(result, version)

    def test_run_id_still_unchanged(self):
        run_id = "20260824" + "-" + "153000" + "-" + "a1b2c3"
        result = _sanitize_for_openrouter_content_filter(run_id)
        self.assertEqual(result, run_id)


if __name__ == "__main__":
    unittest.main()
