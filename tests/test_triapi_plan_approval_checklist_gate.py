import io
import unittest
from unittest import mock

from scripts import triapi


class TestTriapiPlanApprovalChecklistGate(unittest.TestCase):
    """Regression coverage for the 2026-09-04 fix: cmd_plan() must refuse
    'approve' on a turn with no '- [ ] ' checklist content (e.g. a bare
    clarifying question), since a blind piped 'approve' -- needed because
    'triapi plan' requires an interactive terminal -- would otherwise be
    consumed by the question's own approval prompt, saving the question
    text as the run's plan_text and appending it into the target repo's
    AGENTS.md as if it were a real plan. See the escaped-live incident on
    SemAI (run 20260904-114233-213429) in CARRYOVER.md."""

    def _new_run(self):
        return {"run_id": "run-x", "prompt": "p", "project_dir": "/x"}

    def test_blind_piped_approve_on_question_turn_aborts(self):
        # Only one input() answer available (as a blind pipe would give).
        # The question turn is long enough to dodge detect_degenerate_plan's
        # short-response flag, isolating this test to the checklist gate.
        question_turn = (
            "Should the plan update the README to reflect the actual live "
            "codebase, or should it strictly follow the feature list you "
            "provided instead of what the code actually does?"
        )
        with (
            mock.patch.object(triapi.agents_md_gate, "find_incomplete_plan", return_value=None),
            mock.patch.object(triapi.dispatcher, "new_run", return_value=self._new_run()),
            mock.patch.object(
                triapi.planner, "plan_turn",
                return_value={"status": "ok", "text": question_turn, "session_id": "s", "notional_cost_usd": 0.0},
            ),
            mock.patch("builtins.input", side_effect=["approve", EOFError()]),
            mock.patch.object(triapi.dispatcher, "save_run") as save_run_mock,
            mock.patch.object(triapi.agents_md_gate, "append_plan") as append_plan_mock,
            mock.patch("sys.stdout", io.StringIO()),
        ):
            triapi.cmd_plan("do something", "/some/project")
        append_plan_mock.assert_not_called()
        self.assertEqual(save_run_mock.call_args.args[0]["status"], "failed")

    def test_approve_on_question_turn_then_cancel(self):
        question_turn = (
            "Should the plan update the README to reflect the actual live "
            "codebase, or should it strictly follow the feature list you "
            "provided instead of what the code actually does?"
        )
        with (
            mock.patch.object(triapi.agents_md_gate, "find_incomplete_plan", return_value=None),
            mock.patch.object(triapi.dispatcher, "new_run", return_value=self._new_run()),
            mock.patch.object(
                triapi.planner, "plan_turn",
                return_value={"status": "ok", "text": question_turn, "session_id": "s", "notional_cost_usd": 0.0},
            ),
            mock.patch("builtins.input", side_effect=["approve", "cancel"]),
            mock.patch.object(triapi.dispatcher, "save_run") as save_run_mock,
            mock.patch.object(triapi.agents_md_gate, "append_plan") as append_plan_mock,
            mock.patch("sys.stdout", io.StringIO()),
        ):
            triapi.cmd_plan("do something", "/some/project")
        append_plan_mock.assert_not_called()
        self.assertEqual(save_run_mock.call_args.args[0]["status"], "cancelled")

    def test_approve_on_question_turn_then_answer_reaches_next_turn(self):
        # After refusing 'approve' on the question, real feedback should
        # feed back into the outer planning loop (a second call to
        # plan_turn), not just abort.
        question_turn = (
            "Should the plan update the README to reflect the actual live "
            "codebase, or should it strictly follow the feature list you "
            "provided instead of what the code actually does?"
        )
        good_text = (
            "1. Phase 1: Add Hello World\n"
            "- [ ] `scripts/triapi.py`: Insert print(\"hello\") at the top of "
            "main(). Verify with `python3 -m py_compile scripts/triapi.py`.\n"
        )
        plan_turn_mock = mock.Mock(
            side_effect=[
                {"status": "ok", "text": question_turn, "session_id": "s", "notional_cost_usd": 0.0},
                {"status": "ok", "text": good_text, "session_id": "s", "notional_cost_usd": 0.0},
            ]
        )
        with (
            mock.patch.object(triapi.agents_md_gate, "find_incomplete_plan", return_value=None),
            mock.patch.object(triapi.dispatcher, "new_run", return_value=self._new_run()),
            mock.patch.object(triapi.planner, "plan_turn", plan_turn_mock),
            mock.patch(
                "builtins.input",
                side_effect=["approve", "reflect the actual live codebase", "approve"],
            ),
            mock.patch.object(triapi.dispatcher, "save_run"),
            mock.patch.object(triapi.agents_md_gate, "append_plan") as append_plan_mock,
            mock.patch("sys.stdout", io.StringIO()),
        ):
            triapi.cmd_plan("do something", "/some/project")
        append_plan_mock.assert_called_once()
        self.assertEqual(plan_turn_mock.call_count, 2)


if __name__ == "__main__":
    unittest.main()
