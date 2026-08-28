from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.dispatcher import _resolve_dynamic_target, dispatch


class DispatcherDynamicTargetResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write_files(self, files: list[str]) -> None:
        for file_path in files:
            path = self.repo_root / file_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()

    @patch('scripts.dispatcher.subprocess.run')
    def test_resolve_dynamic_target_passthrough_no_subprocess(
        self, mock_run: Mock
    ) -> None:
        target = 'docs/carryover/plan.md'
        result = _resolve_dynamic_target(target, str(self.repo_root))
        mock_run.assert_not_called()
        self.assertEqual(result, target)

    def test_resolve_dynamic_target_expands_real_shell_expression(self) -> None:
        self._write_files(["docs/carryover/index.json"])
        (self.repo_root / "docs" / "carryover" / "index.json").write_text(
            json.dumps({
                "$schema": "carryover-index-v1",
                "instructions": "Machine-readable index of docs/carryover/. Read 'active' file first, always -- it is the only required read to resume work. Read a 'history' entry only if the current task specifically needs that topic. Never read every file. To resume: jq -r '.active' docs/carryover/index.json, then read that file.",
                "active": "20260827-foo.md",
            }),
            encoding="utf-8"
        )
        target = 'docs/carryover/$(jq -r ".active" docs/carryover/index.json)'
        expected_result = 'docs/carryover/20260827-foo.md'
        result = _resolve_dynamic_target(target, str(self.repo_root))
        self.assertEqual(result, expected_result)

    @patch('scripts.dispatcher.subprocess.run')
    def test_resolve_dynamic_target_falls_back_on_subprocess_failure(
        self, mock_run: Mock
    ) -> None:
        target = 'docs/carryover/$(unknown_command)'
        mock_run.side_effect = OSError("boom")
        result = _resolve_dynamic_target(target, str(self.repo_root))
        mock_run.assert_called_once()
        self.assertEqual(result, target)

        mock_run.reset_mock()
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="err")
        result = _resolve_dynamic_target(target, str(self.repo_root))
        mock_run.assert_called_once()
        self.assertEqual(result, target)

    @patch('scripts.dispatcher._recheck_regression_flags')
    @patch('scripts.dispatcher.save_run')
    @patch('scripts.dispatcher.regression_guard.hash_file')
    @patch('scripts.dispatcher.librarian_escalate.run')
    @patch('scripts.dispatcher.load_tiers')
    def test_dispatch_uses_resolved_target_for_doc_item(
        self,
        mock_load_tiers: Mock,
        mock_librarian_run: Mock,
        mock_hash_file: Mock,
        mock_save_run: Mock,
        mock_recheck_regression_flags: Mock
    ) -> None:
        mock_recheck_regression_flags.return_value = False
        state = {
            "run_id": "test_run",
            "project_dir": str(self.repo_root),
            "breakdown": {
                "phases": [
                    {
                        "name": "Phase 1",
                        "items": [
                            {
                                "target": 'docs/carryover/$(cat somefile)',
                                "description": "Update document"
                            }
                        ]
                    }
                ]
            },
            "results": []
        }
        mock_load_tiers.return_value = {
            "tier_5_librarian": {
                "enabled": True,
                "target_globs": ["*.md", "docs/**"]
            }
        }

        (self.repo_root / "somefile").write_text(
            "expected_path",
            encoding="utf-8"
        )

        mock_librarian_run.return_value = {
            "status": "success",
            "resolved_by": "tier_5"
        }

        dispatch(state)
        expected_call_args = mock_librarian_run.call_args_list[0].kwargs

        self.assertEqual(expected_call_args["target"], "docs/carryover/expected_path")

    @patch('scripts.dispatcher._recheck_regression_flags')
    @patch('scripts.dispatcher.save_run')
    @patch('scripts.dispatcher.regression_guard.hash_file')
    @patch('scripts.dispatcher.librarian_escalate.run')
    @patch('scripts.dispatcher.load_tiers')
    def test_dispatch_passes_item_build_cmd_as_verify_cmd_for_doc_item(
        self,
        mock_load_tiers: Mock,
        mock_librarian_run: Mock,
        mock_hash_file: Mock,
        mock_save_run: Mock,
        mock_recheck_regression_flags: Mock
    ) -> None:
        """Regression for a real false-success bug (2026-08-28): dispatch()
        called librarian_escalate.run() without verify_cmd=, so its own
        verify_cmd_resolved fell through to tier_5_librarian.verify_command
        (null in config) then the literal no-op "true" -- the item's real
        build_cmd (e.g. a content-asserting check confirming the intended
        file actually changed) was never run at all, and "success" was
        reported unconditionally regardless of what actually landed on
        disk. Confirmed live: a doc update reported success twice while
        writing to a wrong resolved path; the item's own build_cmd would
        have caught it immediately had it run."""
        mock_recheck_regression_flags.return_value = False
        expected_build_cmd = "test -f docs/notes.md && grep -q expected docs/notes.md"
        state = {
            "run_id": "test_run",
            "project_dir": str(self.repo_root),
            "breakdown": {
                "phases": [
                    {
                        "name": "Phase 1",
                        "items": [
                            {
                                "target": "docs/notes.md",
                                "description": "Update document",
                                "build_cmd": expected_build_cmd,
                            }
                        ]
                    }
                ]
            },
            "results": []
        }
        mock_load_tiers.return_value = {
            "tier_5_librarian": {
                "enabled": True,
                "target_globs": ["*.md", "docs/**"]
            }
        }

        mock_librarian_run.return_value = {
            "status": "success",
            "resolved_by": "tier_5"
        }

        dispatch(state)
        call_kwargs = mock_librarian_run.call_args_list[0].kwargs

        self.assertEqual(call_kwargs["verify_cmd"], expected_build_cmd)
