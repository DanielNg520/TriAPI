import io
import unittest
from unittest import mock

from scripts import triapi


class TestTriapiFlaggedApprovalGate(unittest.TestCase):
    """Regression coverage for the flagged-plan double-confirm gate
    (queue item 5, 2026-08-28): cmd_plan() must never let a single
    'approve' auto-approve a turn planner.detect_degenerate_plan() flags,
    and a blind piped single-line 'approve' (EOFError on the second
    input() call) must abort instead of approving."""

    def _new_run(self):
        return {"run_id": "run-x", "prompt": "p", "project_dir": "/x"}

    def test_flagged_plan_single_approve_is_not_enough(self):
        # First input() call is 'approve' (should NOT approve immediately
        # since the turn is flagged); second input() call (the explicit
        # re-confirmation) is 'cancel'.
        with (
            mock.patch.object(triapi.agents_md_gate, "find_incomplete_plan", return_value=None),
            mock.patch.object(triapi.dispatcher, "new_run", return_value=self._new_run()),
            mock.patch.object(
                triapi.planner, "plan_turn",
                # "ok" alone is < _MIN_PLAN_TEXT_CHARS -- always flagged.
                return_value={"status": "ok", "text": "ok", "session_id": "s", "notional_cost_usd": 0.0},
            ),
            mock.patch("builtins.input", side_effect=["approve", "cancel"]),
            mock.patch.object(triapi.dispatcher, "save_run"),
            mock.patch.object(triapi.agents_md_gate, "append_plan") as append_plan_mock,
            mock.patch("sys.stdout", io.StringIO()),
        ):
            triapi.cmd_plan("do something", "/some/project")
        append_plan_mock.assert_not_called()

    def test_flagged_plan_double_approve_confirms(self):
        with (
            mock.patch.object(triapi.agents_md_gate, "find_incomplete_plan", return_value=None),
            mock.patch.object(triapi.dispatcher, "new_run", return_value=self._new_run()),
            mock.patch.object(
                triapi.planner, "plan_turn",
                return_value={"status": "ok", "text": "ok", "session_id": "s", "notional_cost_usd": 0.0},
            ),
            mock.patch("builtins.input", side_effect=["approve", "approve"]),
            mock.patch.object(triapi.dispatcher, "save_run"),
            mock.patch.object(triapi.agents_md_gate, "append_plan") as append_plan_mock,
            mock.patch("sys.stdout", io.StringIO()),
        ):
            triapi.cmd_plan("do something", "/some/project")
        append_plan_mock.assert_called_once()

    def test_blind_piped_single_approve_on_flagged_plan_aborts(self):
        # Only one input() answer available (as a blind pipe would give) --
        # the second input() call for re-confirmation must hit EOFError
        # and abort, never silently approve.
        with (
            mock.patch.object(triapi.agents_md_gate, "find_incomplete_plan", return_value=None),
            mock.patch.object(triapi.dispatcher, "new_run", return_value=self._new_run()),
            mock.patch.object(
                triapi.planner, "plan_turn",
                return_value={"status": "ok", "text": "ok", "session_id": "s", "notional_cost_usd": 0.0},
            ),
            mock.patch("builtins.input", side_effect=["approve", EOFError()]),
            mock.patch.object(triapi.dispatcher, "save_run") as save_run_mock,
            mock.patch.object(triapi.agents_md_gate, "append_plan") as append_plan_mock,
            mock.patch("sys.stdout", io.StringIO()),
        ):
            triapi.cmd_plan("do something", "/some/project")
        append_plan_mock.assert_not_called()
        self.assertEqual(save_run_mock.call_args.args[0]["status"], "failed")

    def test_unflagged_plan_single_approve_still_works(self):
        good_text = (
            "1. Phase 1: Add Hello World\n"
            "- [ ] `scripts/triapi.py`: Insert print(\"hello\") at the top of "
            "main(). Verify with `python3 -m py_compile scripts/triapi.py`.\n"
        )
        with (
            mock.patch.object(triapi.agents_md_gate, "find_incomplete_plan", return_value=None),
            mock.patch.object(triapi.dispatcher, "new_run", return_value=self._new_run()),
            mock.patch.object(
                triapi.planner, "plan_turn",
                return_value={"status": "ok", "text": good_text, "session_id": "s", "notional_cost_usd": 0.0},
            ),
            mock.patch("builtins.input", side_effect=["approve"]),
            mock.patch.object(triapi.dispatcher, "save_run"),
            mock.patch.object(triapi.agents_md_gate, "append_plan") as append_plan_mock,
            mock.patch("sys.stdout", io.StringIO()),
        ):
            triapi.cmd_plan("do something", "/some/project")
        append_plan_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
