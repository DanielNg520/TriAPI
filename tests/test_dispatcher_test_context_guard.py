"""Regression tests for scripts/dispatcher.py's context_files grounding guard.

Covers _find_anchor_test_file and _apply_test_context_guard -- see CARRYOVER.md
queue item's "context_files grounding guard" entry for the two real 2026-08-18
incidents this closes (tests/test_hivemind_util.py missing scripts/hivemind_util.py
in context_files; tests/test_judge.py missing a style anchor).
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.dispatcher import _apply_test_context_guard, _find_anchor_test_file


class DispatcherTestContextGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temp_dir.name)
        self.tests_dir = self.repo_root / "tests"
        self.scripts_dir = self.repo_root / "scripts"
        self.tests_dir.mkdir()
        self.scripts_dir.mkdir()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write_files(self, files: list[str]) -> None:
        for file_path in files:
            (self.repo_root / file_path).touch()

    def test_find_anchor_test_file_prefers_branch_features(self) -> None:
        self._write_files(["tests/test_branch_features.py", "tests/test_other.py"])
        anchor = _find_anchor_test_file(str(self.repo_root))
        self.assertEqual(anchor, str(self.tests_dir / "test_branch_features.py"))

    def test_find_anchor_test_file_falls_back_to_sorted_other(self) -> None:
        self._write_files(["tests/test_zzz.py", "tests/test_aaa.py"])
        anchor = _find_anchor_test_file(str(self.repo_root))
        self.assertEqual(anchor, str(self.tests_dir / "test_aaa.py"))

    def test_find_anchor_test_file_none_when_tests_dir_empty(self) -> None:
        anchor = _find_anchor_test_file(str(self.repo_root))
        self.assertIsNone(anchor)

    def test_find_anchor_test_file_none_when_tests_dir_missing(self) -> None:
        empty_repo = self.repo_root / "empty_repo"
        empty_repo.mkdir()
        anchor = _find_anchor_test_file(str(empty_repo))
        self.assertIsNone(anchor)

    def test_apply_test_context_guard_adds_companion_and_anchor(self) -> None:
        # The exact 2026-08-18 incident shape: tests/test_hivemind_util.py's
        # item never listed scripts/hivemind_util.py in context_files.
        self._write_files([
            "scripts/hivemind_util.py",
            "tests/test_branch_features.py",
        ])
        items = [{"target": "tests/test_hivemind_util.py", "description": "x"}]
        result = _apply_test_context_guard(items, str(self.repo_root))
        self.assertIsNone(result)
        self.assertIn(
            str(self.scripts_dir / "hivemind_util.py"), items[0]["context_files"]
        )
        self.assertIn(
            str(self.tests_dir / "test_branch_features.py"), items[0]["context_files"]
        )

    def test_apply_test_context_guard_skips_missing_companion(self) -> None:
        self._write_files(["tests/test_branch_features.py"])
        items = [{"target": "tests/test_judge.py", "description": "x"}]
        result = _apply_test_context_guard(items, str(self.repo_root))
        self.assertIsNone(result)
        # No scripts/judge.py exists in this fixture -- must not fabricate the path.
        self.assertNotIn(
            str(self.scripts_dir / "judge.py"), items[0]["context_files"]
        )
        self.assertIn(
            str(self.tests_dir / "test_branch_features.py"), items[0]["context_files"]
        )

    def test_apply_test_context_guard_ignores_non_test_target(self) -> None:
        self._write_files(["tests/test_branch_features.py"])
        items = [{"target": "scripts/foo.py", "description": "x"}]
        result = _apply_test_context_guard(items, str(self.repo_root))
        self.assertIsNone(result)
        self.assertNotIn("context_files", items[0])

    def test_apply_test_context_guard_ignores_git_items(self) -> None:
        self._write_files(["tests/test_branch_features.py"])
        items = [{"git": "commit", "target": "tests/test_hivemind_util.py"}]
        result = _apply_test_context_guard(items, str(self.repo_root))
        self.assertIsNone(result)
        self.assertNotIn("context_files", items[0])

    def test_apply_test_context_guard_no_duplicates_on_repeat_call(self) -> None:
        self._write_files([
            "scripts/hivemind_util.py",
            "tests/test_branch_features.py",
        ])
        items = [{"target": "tests/test_hivemind_util.py", "description": "x"}]
        _apply_test_context_guard(items, str(self.repo_root))
        first_len = len(items[0]["context_files"])
        _apply_test_context_guard(items, str(self.repo_root))
        self.assertEqual(len(items[0]["context_files"]), first_len)

    def test_apply_test_context_guard_rejects_when_no_anchor_exists(self) -> None:
        # tests/ dir exists but has zero test files -- no anchor to ground against.
        items = [{"target": "tests/test_hivemind_util.py", "description": "x"}]
        result = _apply_test_context_guard(items, str(self.repo_root))
        self.assertIsNotNone(result)
        self.assertIsInstance(result, str)


if __name__ == "__main__":
    unittest.main()
