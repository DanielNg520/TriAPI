import unittest
from unittest.mock import MagicMock, mock_open, patch

from scripts.vcb_run import build_planner_prompt, run_vcb


class BuildPlannerPromptTests(unittest.TestCase):
    def test_prompt_contains_skeleton_task_description_and_instructions(self):
        prompt = build_planner_prompt("skeleton text", "task text")

        self.assertIn("skeleton text", prompt)
        self.assertIn("task text", prompt)
        self.assertIn("INSTRUCTIONS:", prompt)
        self.assertIn("Draft correctness-focused logic", prompt)


class RunVcbTests(unittest.TestCase):
    def test_run_vcb_uses_skeleton_planner_file_and_materializer(self):
        repo_path = "repo"
        file_path = "path/to/file.py"
        target_symbol = "target_symbol"
        task_description = "task description"
        skeleton = "skeleton"
        skeleton_draft = "skeleton draft"
        file_content = "file content"
        materialize_return = ("draft", "metadata")

        planner_call_fn = MagicMock(return_value=skeleton_draft)
        materializer_call_fn = MagicMock()
        build_skeleton_mock = MagicMock(return_value=skeleton)
        materialize_mock = MagicMock(return_value=materialize_return)

        with patch("builtins.open", mock_open(read_data=file_content)):
            with patch("scripts.vcb_run.build_skeleton", build_skeleton_mock):
                with patch("scripts.vcb_run.materialize", materialize_mock):
                    result = run_vcb(
                        repo_path,
                        file_path,
                        target_symbol,
                        task_description,
                        planner_call_fn,
                        materializer_call_fn,
                    )

        build_skeleton_mock.assert_called_once_with(repo_path, file_path, target_symbol)
        planner_call_fn.assert_called_once_with(
            build_planner_prompt(skeleton, task_description)
        )
        materialize_mock.assert_called_once_with(
            file_path,
            file_content,
            skeleton_draft,
            task_description,
            materializer_call_fn,
        )
        self.assertEqual(result, materialize_return)
