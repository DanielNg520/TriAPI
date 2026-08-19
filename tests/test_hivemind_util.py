from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.hivemind_util import parse_hivemind, search_hivemind


class TestHivemindUtil(unittest.TestCase):
    def test_parse_well_formed_snippet(self) -> None:
        content = """
Some raw text before the snippet.
<triapi_snippet name="get_user" tags="python, api, user">
def get_user(user_id):
    return {"id": user_id, "name": "Alice"}
</triapi_snippet>
Some raw text after the snippet.
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "hivemind.md"
            filepath.write_text(content, encoding="utf-8")

            snippets = parse_hivemind(str(filepath))
            self.assertEqual(len(snippets), 1)
            self.assertEqual(snippets[0]["name"], "get_user")
            self.assertEqual(snippets[0]["tags"], ["python", "api", "user"])
            self.assertEqual(snippets[0]["code"], 'def get_user(user_id):\n    return {"id": user_id, "name": "Alice"}')

    def test_parse_zero_snippets(self) -> None:
        content = "This file contains some general notes but no triapi_snippet blocks."
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "hivemind.md"
            filepath.write_text(content, encoding="utf-8")

            snippets = parse_hivemind(str(filepath))
            self.assertEqual(snippets, [])

    def test_missing_file_behavior(self) -> None:
        # Non-existent file should return empty list rather than raising an error
        snippets = parse_hivemind("/nonexistent/path/to/hivemind.md")
        self.assertEqual(snippets, [])

    def test_parse_hivemind_os_error(self) -> None:
        # Simulating an OSError during read_text should return empty list safely
        with mock.patch("scripts.hivemind_util.Path.exists", return_value=True):
            with mock.patch("scripts.hivemind_util.Path.read_text", side_effect=OSError):
                snippets = parse_hivemind("dummy.md")
                self.assertEqual(snippets, [])

    def test_search_hivemind_filtering_by_extension(self) -> None:
        mock_snippets = [
            {
                "name": "py_helper",
                "tags": ["python", "helper", "db"],
                "code": "def db_connect(): pass"
            },
            {
                "name": "js_helper",
                "tags": ["javascript", "helper", "db"],
                "code": "function dbConnect() {}"
            }
        ]
        with mock.patch("scripts.hivemind_util.parse_hivemind", return_value=mock_snippets):
            # Search filtering for python
            res_py = search_hivemind("connect to the db helper", ".py")
            self.assertEqual(res_py, "def db_connect(): pass")

            # Search filtering for javascript (without leading dot in search argument)
            res_js = search_hivemind("connect to the db helper", "js")
            self.assertEqual(res_js, "function dbConnect() {}")

    def test_search_hivemind_zero_overlap(self) -> None:
        mock_snippets = [
            {
                "name": "py_helper",
                "tags": ["python", "helper"],
                "code": "def db_connect(): pass"
            }
        ]
        with mock.patch("scripts.hivemind_util.parse_hivemind", return_value=mock_snippets):
            # No matching words in the snippet tags (only language is matched)
            res = search_hivemind("completely unrelated query", ".py")
            self.assertIsNone(res)

    def test_search_hivemind_highest_score(self) -> None:
        mock_snippets = [
            {
                "name": "low_score",
                "tags": ["python", "helper"],
                "code": "low"
            },
            {
                "name": "high_score",
                "tags": ["python", "helper", "db", "auth"],
                "code": "high"
            }
        ]
        with mock.patch("scripts.hivemind_util.parse_hivemind", return_value=mock_snippets):
            res = search_hivemind("db helper query with auth", ".py")
            self.assertEqual(res, "high")
