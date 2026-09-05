"""Tests for the relocation guard Phase 2 hard-fail path.

Reproduces the exact failure shape from run 20260903-064926-265e55: an
item whose description names symbols as being moved/split/extracted, but
the diff deletes one of them without it landing in any target file --
yet the item's own build_cmd reports success. detect_relocation_intent()/
symbol_exists_in_project() (scripts/scope_guard.py) and their call site
in dispatcher.py's dispatch loop must catch this as a hard failure.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from scripts import dispatcher, scope_guard


class RelocationIntentDetectionTests(unittest.TestCase):
    def test_relocation_verb_plus_named_symbols_detected(self) -> None:
        result = scope_guard.detect_relocation_intent(
            "Move TestAlpha and TestBeta from source.py to destination.py"
        )
        self.assertEqual(result, {"TestAlpha", "TestBeta"})

    def test_no_relocation_verb_returns_empty(self) -> None:
        result = scope_guard.detect_relocation_intent("Fix a bug in TestBeta")
        self.assertEqual(result, set())

    def test_method_call_named_after_verb_is_not_relocation_intent(self) -> None:
        # Root cause of the ORIGINAL false build_failed bug this guard's
        # own bug-hunt was for (run 20260904-154839-ccfa17, tracked in
        # knowledge/TECH_DEBT.md): an item description that used
        # `" ".join(build_output.split())` was misread as naming a "split"
        # relocation, and `build_output` (a local variable, not a def/
        # class) was then reported "missing," permanently failing three
        # genuinely successful tier attempts in a row.
        description = (
            "Sanitize build_output so it fits on a single line: strip "
            'newlines and collapse whitespace using " ".join(build_output.split()).'
        )
        result = scope_guard.detect_relocation_intent(description)
        self.assertEqual(result, set())


class SymbolExistsInProjectTests(unittest.TestCase):
    def test_symbol_present_in_some_file_returns_true(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "destination.py").write_text(
                "class TestAlpha:\n    pass\n\nclass TestBeta:\n    pass\n",
                encoding="utf-8",
            )
            self.assertTrue(scope_guard.symbol_exists_in_project(tmp, "TestBeta"))

    def test_symbol_missing_from_every_file_returns_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "destination.py").write_text(
                "class TestAlpha:\n    pass\n",
                encoding="utf-8",
            )
            self.assertFalse(scope_guard.symbol_exists_in_project(tmp, "TestBeta"))


class DispatchRelocationGuardIntegrationTests(unittest.TestCase):
    """Exercises the real hard-fail call site inside dispatcher.dispatch(),
    following this repo's existing DispatcherHookAndFixForwardTests
    mocking conventions (tests/test_branch_features.py)."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.project_dir = self.tmpdir.name
        self.target_file = Path(self.project_dir) / "destination.py"

    def tearDown(self):
        self.tmpdir.cleanup()

    def _state(self, description: str) -> dict:
        return {
            "run_id": "run-reloc-test",
            "project_dir": self.project_dir,
            "status": "planned",
            "breakdown": {
                "phases": [
                    {
                        "name": "Phase 1",
                        "items": [
                            {
                                "description": description,
                                "target": str(self.target_file.relative_to(self.project_dir)),
                                "build_cmd": "echo 'built'",
                                "verify_only": False,
                                "context_files": [],
                            }
                        ],
                    }
                ]
            },
            "results": [],
        }

    @mock.patch("scripts.dispatcher.save_run")
    @mock.patch("scripts.dispatcher.check_tier2_ok", return_value={"ok": True})
    @mock.patch("scripts.dispatcher.run_task")
    @mock.patch("scripts.judge.evaluate_design")
    @mock.patch("scripts.judge.extract_pattern")
    @mock.patch("subprocess.run")
    def test_buggy_relocation_drops_symbol_hard_fails(
        self, mock_run, mock_extract, mock_eval, mock_run_task, mock_check_ok, mock_save
    ):
        # Bug shape: both classes removed from source, only TestAlpha
        # written to the destination target -- build_cmd/run_task still
        # reports success, mirroring the real 20260903-064926-265e55 bug.
        self.target_file.write_text("class TestAlpha:\n    pass\n", encoding="utf-8")
        mock_run_task.return_value = {"status": "success", "resolved_by": "tier_3"}
        mock_eval.return_value = {"status": "ok", "approved": True, "reason": "looks good", "cost_usd": 0.01}
        mock_run.return_value = SimpleNamespace(returncode=0, stdout="diff content", stderr="")

        state = self._state("Move TestAlpha and TestBeta from source.py to destination.py")
        # `reason` is logged, never persisted into state["results"] entries --
        # consistent with every other build_failed/error path in this file
        # (see e.g. orchestrator.py's Tier 1-3 rejection logging), so assert
        # against the log instead of a nonexistent entry field.
        with self.assertLogs("triapi.dispatcher", level="WARNING") as logs:
            dispatcher.dispatch(state)

        self.assertEqual(state["results"][0]["status"], "build_failed")
        self.assertTrue(any("TestBeta" in message for message in logs.output))

    @mock.patch("scripts.dispatcher.save_run")
    @mock.patch("scripts.dispatcher.check_tier2_ok", return_value={"ok": True})
    @mock.patch("scripts.dispatcher.run_task")
    @mock.patch("scripts.judge.evaluate_design")
    @mock.patch("scripts.judge.extract_pattern")
    @mock.patch("subprocess.run")
    def test_successful_relocation_both_symbols_land_not_blocked(
        self, mock_run, mock_extract, mock_eval, mock_run_task, mock_check_ok, mock_save
    ):
        self.target_file.write_text(
            "class TestAlpha:\n    pass\n\nclass TestBeta:\n    pass\n", encoding="utf-8"
        )
        mock_run_task.return_value = {"status": "success", "resolved_by": "tier_3"}
        mock_eval.return_value = {"status": "ok", "approved": True, "reason": "looks good", "cost_usd": 0.01}
        mock_run.return_value = SimpleNamespace(returncode=0, stdout="diff content", stderr="")

        state = self._state("Move TestAlpha and TestBeta from source.py to destination.py")
        dispatcher.dispatch(state)

        self.assertEqual(state["results"][0]["status"], "success")
        self.assertEqual(state["status"], "completed")

    @mock.patch("scripts.dispatcher.save_run")
    @mock.patch("scripts.dispatcher.check_tier2_ok", return_value={"ok": True})
    @mock.patch("scripts.dispatcher.librarian_escalate.run")
    @mock.patch("subprocess.run")
    def test_doc_target_relocation_prose_not_blocked(
        self, mock_run, mock_librarian_run, mock_check_ok, mock_save
    ):
        # Real bug shape (SemAI run 20260903-133525-cb514e, item p2-i0): a
        # tier_5_librarian doc edit whose own build_cmd already passes gets
        # force-failed because its description says a data filename was
        # "moved" between directories -- detect_relocation_intent() has no
        # way to tell that apart from a real code-symbol move, and no
        # Python symbol named after a data filename will ever be found.
        doc_target = Path(self.project_dir) / "MAPPING.md"
        doc_target.write_text("# Mapping\n", encoding="utf-8")
        mock_librarian_run.return_value = {
            "status": "success", "resolved_by": "tier_5", "changed": False, "via": "model_fresh",
        }
        mock_run.return_value = SimpleNamespace(returncode=0, stdout="diff content", stderr="")

        state = self._state(
            "Add a brief entry to MAPPING.md documenting that EmailRules.md "
            "was moved from 10-Memory/Rules/ to .state-semai/"
        )
        state["breakdown"]["phases"][0]["items"][0]["target"] = "MAPPING.md"
        dispatcher.dispatch(state)

        self.assertEqual(state["results"][0]["status"], "success")
        self.assertEqual(state["status"], "completed")
