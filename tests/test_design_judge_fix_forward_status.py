import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import scripts.dispatcher as dispatcher


class TestDesignJudgeFixForwardStatus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.target_file_path = Path(cls.temp_dir.name) / "test_target.py"
        cls.original_content = b'original content\n'
        cls.fixed_content = b'tier 3 rewrite\n'

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def setUp(self):
        self.target_file = Path(self.target_file_path)
        with open(self.target_file, "wb") as f:
            f.write(self.original_content)

        self.item = {
            "target": str(self.target_file),
            "description": "fix a bug"
        }
        self.state = {"project_dir": self.temp_dir.name}
        self.task_id = "task1"

    def tearDown(self):
        if os.path.exists(self.target_file):
            os.remove(self.target_file)
        with open(self.target_file, "wb") as f:
            f.write(self.original_content)

    @patch.object(dispatcher, "handle_fix_forward")
    @patch.object(dispatcher, "_git_diff_for", return_value="diff --git a/test_target.py b/test_target.py")
    @patch.object(dispatcher.judge, "extract_pattern")
    @patch.object(dispatcher.judge, "evaluate_design")
    def test_approve_no_fix_forward_needed(self, mock_evaluate, mock_extract_pattern, mock_git_diff, mock_handle_fix):
        result = {"status": "success", "resolved_by": "tier_5"}
        mock_evaluate.return_value = {
            "status": "ok",
            "approved": True,
            "reason": "looks good",
            "cost_usd": 0.0,
        }

        result = dispatcher._run_design_judge(self.item, result, self.state, self.task_id)

        mock_evaluate.assert_called_once()
        self.assertEqual(result["status"], "success")
        mock_handle_fix.assert_not_called()

    @patch.object(dispatcher, "run_build", return_value=(True, ""))
    @patch.object(dispatcher.tier3_escalate, "escalate", autospec=True)
    @patch.object(dispatcher, "_git_diff_for", return_value="diff --git a/test_target.py b/test_target.py")
    @patch.object(dispatcher.judge, "evaluate_design")
    def test_reject_with_successful_fix_forward(self, mock_evaluate, mock_git_diff, mock_escalate, mock_run_build):
        result = {"status": "success", "resolved_by": "tier_5"}
        mock_evaluate.return_value = {
            "status": "ok",
            "approved": False,
            "reason": "needs fix",
            "cost_usd": 0.0,
        }

        def fake_escalate(*args, **kwargs):
            self.target_file.write_bytes(self.fixed_content)
            return {"status": "fix_applied"}

        mock_escalate.side_effect = fake_escalate

        result = dispatcher._run_design_judge(self.item, result, self.state, self.task_id)

        mock_evaluate.assert_called_once()
        self.assertEqual(result["status"], "success")
        mock_escalate.assert_called_once()
        mock_run_build.assert_called_once()
        self.assertEqual(self.target_file.read_bytes(), self.fixed_content)

    @patch.object(dispatcher, "run_build", return_value=(True, ""))
    @patch.object(dispatcher.tech_debt, "log_tech_debt")
    @patch.object(dispatcher.tier3_escalate, "escalate", autospec=True)
    @patch.object(dispatcher, "_git_diff_for", return_value="diff --git a/test_target.py b/test_target.py")
    @patch.object(dispatcher.judge, "evaluate_design")
    def test_reject_with_unsuccessful_fix_forward(self, mock_evaluate, mock_git_diff, mock_escalate, mock_log_debt, mock_run_build):
        result = {"status": "success", "resolved_by": "tier_5"}
        mock_evaluate.return_value = {
            "status": "ok",
            "approved": False,
            "reason": "needs fix",
            "cost_usd": 0.0,
        }

        def fake_escalate(*args, **kwargs):
            self.target_file.write_bytes(self.fixed_content)
            return {"status": "fix_rejected"}

        mock_escalate.side_effect = fake_escalate

        result = dispatcher._run_design_judge(self.item, result, self.state, self.task_id)

        mock_evaluate.assert_called_once()
        self.assertEqual(result["status"], "build_failed")
        self.assertIsNone(result["resolved_by"])
        mock_escalate.assert_called_once()
        mock_log_debt.assert_called_once()
        self.assertEqual(self.target_file.read_bytes(), self.original_content)

if __name__ == '__main__':
    unittest.main()
