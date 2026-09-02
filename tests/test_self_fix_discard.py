"""Regression tests for triapi.cmd_self_fix_discard."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import self_fix, triapi


class SelfFixDiscardTests(unittest.TestCase):
    def test_discard_bug_report_only(self) -> None:
        """Discarding a bug-report-only entry (no linked run) should delete the bug report file and not crash."""
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(self_fix, "BUGS_DIR", Path(tmp)):
            bug_report_path = Path(tmp) / "orphan-bug.json"
            bug_report_path.write_text(
                json.dumps({"exception_type": "RuntimeError", "exception_message": "boom"}),
                encoding="utf-8",
            )

            buf = io.StringIO()
            with (
                mock.patch.object(triapi, "_find_self_fix_run", return_value=None),
                mock.patch.object(triapi, "_resolve_bug_report", return_value=bug_report_path),
                mock.patch("sys.stdout", buf),
            ):
                triapi.cmd_self_fix_discard("orphan-bug-id")

            self.assertFalse(bug_report_path.exists())
            out = buf.getvalue()
            self.assertNotIn("nothing found for", out)
            self.assertIn("Discarded bug report", out)

    def test_discard_drafted_run_only(self) -> None:
        """Discarding a drafted-run-only entry (no resolvable bug report file) should clear the run state and not crash."""
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(self_fix, "BUGS_DIR", Path(tmp)):
            state = {
                "run_id": "drafted-run",
                "status": "self_fix_drafted",
                "plan_text": "some plan",
                "project_dir": str(self_fix.TRIAPI_ROOT.resolve()),
            }

            buf = io.StringIO()
            with (
                mock.patch.object(triapi, "_find_self_fix_run", return_value=state),
                mock.patch.object(triapi, "_resolve_bug_report", return_value=None),
                mock.patch("sys.stdout", buf),
            ):
                triapi.cmd_self_fix_discard("drafted-run-id")

            out = buf.getvalue()
            self.assertNotIn("nothing found for", out)
            self.assertNotIn("Traceback", out)

    def test_discard_both_together(self) -> None:
        """Discarding both a bug report and a drafted run together in one call should delete both."""
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(self_fix, "BUGS_DIR", Path(tmp)):
            bug_report_path = Path(tmp) / "bug-report.json"
            bug_report_path.write_text(
                json.dumps({"exception_type": "RuntimeError", "exception_message": "boom"}),
                encoding="utf-8",
            )

            state = {
                "run_id": "both-run",
                "status": "self_fix_drafted",
                "plan_text": "some plan",
                "project_dir": str(self_fix.TRIAPI_ROOT.resolve()),
            }

            buf = io.StringIO()
            with (
                mock.patch.object(triapi, "_find_self_fix_run", return_value=state),
                mock.patch.object(triapi, "_resolve_bug_report", return_value=bug_report_path),
                mock.patch("sys.stdout", buf),
            ):
                triapi.cmd_self_fix_discard("both-run-id")

            self.assertFalse(bug_report_path.exists())
            out = buf.getvalue()
            self.assertIn("Discarded bug report", out)
            self.assertNotIn("nothing found for", out)

    def test_discard_nonexistent_bug_id(self) -> None:
        """Discarding a nonexistent bug_id must not crash and must print the 'nothing found for <bug_id>' message."""
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(self_fix, "BUGS_DIR", Path(tmp)):
            buf = io.StringIO()
            with (
                mock.patch.object(triapi, "_find_self_fix_run", return_value=None),
                mock.patch.object(triapi, "_resolve_bug_report", return_value=None),
                mock.patch("sys.stdout", buf),
            ):
                triapi.cmd_self_fix_discard("nonexistent-bug-id")

            out = buf.getvalue()
            self.assertIn("nothing found for nonexistent-bug-id", out)

    def test_refuse_to_delete_non_drafted_run(self) -> None:
        """Refusing to delete a run whose status is anything other than 'self_fix_drafted' should still delete the bug report file if any, and skip only the run-state deletion."""
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(self_fix, "BUGS_DIR", Path(tmp)):
            state = {
                "run_id": "planned-run",
                "status": "planned",
                "plan_text": "some plan",
                "project_dir": str(self_fix.TRIAPI_ROOT.resolve()),
            }
            bug_report_path = Path(tmp) / "bug-report.json"
            bug_report_path.write_text(
                json.dumps({"exception_type": "RuntimeError", "exception_message": "boom"}),
                encoding="utf-8",
            )

            buf = io.StringIO()
            with (
                mock.patch.object(triapi, "_find_self_fix_run", return_value=state),
                mock.patch.object(triapi, "_resolve_bug_report", return_value=bug_report_path),
                mock.patch.object(triapi.dispatcher, "save_run") as save_run,
                mock.patch("sys.stdout", buf),
            ):
                triapi.cmd_self_fix_discard("planned-run-id")

            # Bug report file should have been deleted
            self.assertFalse(bug_report_path.exists())
            # Run-state deletion should be skipped; save_run should not be called
            save_run.assert_not_called()

            out = buf.getvalue()
            self.assertIn("Discarded bug report", out)


class TechDebtBuildCmdTests(unittest.TestCase):
    """Direct, hermetic coverage for triapi._tech_debt_build_cmd -- no
    TECH_DEBT.md/dispatcher involvement, so it can't accidentally read real
    project state (the earlier version of this test did, via cmd_tech_debt's
    hardcoded TECH_DEBT_PATH, and passed for the wrong reason)."""

    def test_absolute_test_path_gets_module_specific_unittest_run(self) -> None:
        build_cmd = triapi._tech_debt_build_cmd(
            "/home/dyne/Documents/Coding/TriAPI/tests/test_llm_client_sanitize.py"
        )
        self.assertIn("py_compile", build_cmd)
        self.assertIn("unittest tests.test_llm_client_sanitize -v", build_cmd)

    def test_relative_test_path_gets_module_specific_unittest_run(self) -> None:
        build_cmd = triapi._tech_debt_build_cmd("tests/test_something.py")
        self.assertIn("py_compile", build_cmd)
        self.assertIn("unittest tests.test_something -v", build_cmd)

    def test_non_test_path_falls_back_to_shared_suite(self) -> None:
        build_cmd = triapi._tech_debt_build_cmd(
            "/home/dyne/Documents/Coding/TriAPI/scripts/non_test.py"
        )
        self.assertIn("py_compile", build_cmd)
        self.assertIn(
            "PYTHONPATH=. python3 -m unittest tests.test_branch_features tests.test_tier5_librarian -v",
            build_cmd,
        )
