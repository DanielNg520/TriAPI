"""Regression tests for mock.patch target/import binding mismatches."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import mock_patch_lint


class MockPatchLintTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temp_dir.name)
        self.scripts_dir = self.repo_root / "scripts"
        self.scripts_dir.mkdir()

        # Fixture modules. module_b re-imports function_a via a name-binding
        # import, which is exactly the mismatch mock_patch_lint detects.
        (self.scripts_dir / "module_a.py").write_text(
            "def function_a(): pass\n", encoding="utf-8"
        )
        (self.scripts_dir / "module_b.py").write_text(
            "from scripts.module_a import function_a\n", encoding="utf-8"
        )
        self.assertTrue((self.scripts_dir / "module_a.py").is_file())
        self.assertTrue((self.scripts_dir / "module_b.py").is_file())

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _run_main(self, test_file: Path) -> int:
        with mock.patch("sys.stdout", io.StringIO()), mock.patch(
            "sys.stderr", io.StringIO()
        ):
            return mock_patch_lint.main(
                [str(test_file), f"--repo-root={self.repo_root}"]
            )

    def test_flags_wrong_patch_target(self) -> None:
        test_file = self.repo_root / "test_script.py"
        test_file.write_text(
            "from scripts import module_b\n"
            "from unittest import mock\n"
            "\n"
            '@mock.patch("scripts.module_a.function_a")\n'
            "def test_function() -> None:\n"
            "    module_b.function_a()\n",
            encoding="utf-8",
        )

        issues = mock_patch_lint.find_issues(test_file, self.repo_root)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["wrong_target"], "scripts.module_a.function_a")
        self.assertEqual(
            issues[0]["correct_targets"], ["scripts.module_b.function_a"]
        )
        code = self._run_main(test_file)
        self.assertEqual(code, 1)

    def test_passes_correct_patch_target(self) -> None:
        test_file = self.repo_root / "test_script.py"
        test_file.write_text(
            "from scripts import module_b\n"
            "from unittest import mock\n"
            "\n"
            '@mock.patch("scripts.module_b.function_a")\n'
            "def test_function() -> None:\n"
            "    module_b.function_a()\n",
            encoding="utf-8",
        )

        self.assertEqual(mock_patch_lint.find_issues(test_file, self.repo_root), [])

        code = self._run_main(test_file)
        self.assertEqual(code, 0)

    def test_cli_exit_codes(self) -> None:
        test_file_with_issues = self.repo_root / "test_script_with_issues.py"
        test_file_with_issues.write_text(
            "from scripts import module_b\n"
            "from unittest import mock\n"
            "\n"
            '@mock.patch("scripts.module_a.function_a")\n'
            "def test_function() -> None:\n"
            "    module_b.function_a()\n",
            encoding="utf-8",
        )

        test_file_without_issues = self.repo_root / "test_script_without_issues.py"
        test_file_without_issues.write_text(
            "from scripts import module_b\n"
            "from unittest import mock\n"
            "\n"
            '@mock.patch("scripts.module_b.function_a")\n'
            "def test_function() -> None:\n"
            "    module_b.function_a()\n",
            encoding="utf-8",
        )

        # Test with issues
        self.assertEqual(self._run_main(test_file_with_issues), 1)

        # Test without issues
        self.assertEqual(self._run_main(test_file_without_issues), 0)
