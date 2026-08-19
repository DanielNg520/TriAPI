"""Regression tests for the Tier 4 file-size ceiling guard and oversize
(timeout / truncated-response) escalation shortcut.

Covers scripts.dispatcher._enforce_file_size_ceiling (rejects a plan item
targeting a file already at/over TIER4_MAX_CONTEXT_CHARS on disk) and
scripts.tier4_worker._tier4_fail's is_oversize_failure fast-path, which
escalates a timeout or truncated-response failure after exactly 1
consecutive failure instead of the normal 2.
"""

import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest import mock

from scripts.tier4_worker import run
from scripts.state import clear_state
from scripts.dispatcher import _enforce_file_size_ceiling, TIER4_MAX_CONTEXT_CHARS


TIER4_CONFIG = {
    "tier_4_worker": {
        "models": {"default": "test-model"},
        "default_model": "default",
        "build_commands": ["echo test"],
        "endpoint": "http://localhost:11434",
    },
    "escalation_rules": {"tier4_to_tier3": {"threshold": 2}},
}


class TestFileSizeCeilingAndOversizeEscalation(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.repo_root = Path(self.temp_dir.name)
        self.target_path = self.repo_root / "test_file.cpp"
        self.nonexistent_target_path = self.repo_root / "nonexistent_file.cpp"
        self.task_ids: list[str] = []

    def tearDown(self) -> None:
        for task_id in self.task_ids:
            clear_state(task_id)
        self.temp_dir.cleanup()

    def _task_id(self, name: str) -> str:
        self.task_ids.append(name)
        clear_state(name)
        return name

    def _write_large_file(self, path: Path, size: int) -> None:
        with open(path, "w") as f:
            f.write("a" * size)

    def _run_with_mocks(self, task_id: str, run_build_return=None, extract_code_return="__unset__"):
        patches = [
            mock.patch("scripts.tier4_worker.load_tiers", return_value=TIER4_CONFIG),
            mock.patch("scripts.tier4_worker.call_ollama", return_value={"response": "no fenced code here", "prompt_eval_count": 0, "eval_count": 0}),
            mock.patch("scripts.tier4_worker.hivemind_util.search_hivemind", return_value=None),
            mock.patch("scripts.tier4_worker.log_cost"),
            mock.patch("scripts.tier4_worker.content_guard.check_write", return_value={"ok": True}),
        ]
        if run_build_return is not None:
            patches.append(mock.patch("scripts.tier4_worker.run_build", return_value=run_build_return))
        if extract_code_return != "__unset__":
            patches.append(mock.patch("scripts.tier4_worker.extract_code", return_value=extract_code_return))
        for p in patches:
            p.start()
        try:
            return run(task_id, "Fix the compile error", str(self.nonexistent_target_path))
        finally:
            for p in patches:
                p.stop()

    def _phases(self, target: str) -> list[dict]:
        return [{"name": "p", "items": [{"target": target}]}]

    def test_enforce_file_size_ceiling_rejects_existing_large_file(self):
        self._write_large_file(self.target_path, TIER4_MAX_CONTEXT_CHARS + 1000)
        error = _enforce_file_size_ceiling(self._phases("test_file.cpp"), str(self.repo_root))
        self.assertIsNotNone(error)
        self.assertIn("test_file.cpp", error)
        self.assertIn(str(TIER4_MAX_CONTEXT_CHARS + 1000), error)

    def test_enforce_file_size_ceiling_ignores_small_existing_file(self):
        self._write_large_file(self.target_path, TIER4_MAX_CONTEXT_CHARS - 1000)
        result = _enforce_file_size_ceiling(self._phases("test_file.cpp"), str(self.repo_root))
        self.assertIsNone(result)

    def test_enforce_file_size_ceiling_ignores_nonexistent_file(self):
        result = _enforce_file_size_ceiling(self._phases("nonexistent_file.cpp"), str(self.repo_root))
        self.assertIsNone(result)

    def test_tier4_timeout_failure_escalates_after_one_consecutive_failure(self):
        task_id = self._task_id("timeout_task")
        build_output = "Command timed out after 120s: ./run_tests.sh"
        result = self._run_with_mocks(task_id, run_build_return=(False, build_output))
        self.assertEqual(result["consecutive_failures"], 1)
        self.assertEqual(result["status"], "escalate")

    def test_truncated_response_failure_escalates_after_one_consecutive_failure(self):
        task_id = self._task_id("truncated_task")
        result = self._run_with_mocks(task_id, extract_code_return=None)
        self.assertEqual(result["consecutive_failures"], 1)
        self.assertEqual(result["status"], "escalate")

    def test_ordinary_build_failed_escalates_after_two_consecutive_failures(self):
        task_id = self._task_id("ordinary_task")
        build_output = "Compilation error: syntax error."

        result = self._run_with_mocks(task_id, run_build_return=(False, build_output))
        self.assertEqual(result["consecutive_failures"], 1)
        self.assertEqual(result["status"], "build_failed")

        result = self._run_with_mocks(task_id, run_build_return=(False, build_output))
        self.assertEqual(result["consecutive_failures"], 2)
        self.assertEqual(result["status"], "escalate")


if __name__ == "__main__":
    unittest.main()
