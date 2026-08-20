"""Regression tests for the Tier 4 file-size ceiling guard and oversize
(timeout / truncated-response) escalation shortcut.

Covers scripts.dispatcher._enforce_file_size_ceiling (marks a plan item
targeting a file already at/over TIER4_MAX_CONTEXT_CHARS on disk to skip
Tier 4 and go straight to Tier 3, with an appended instruction to shrink
the file rather than just patch it in place) and
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
from scripts.dispatcher import (
    _enforce_file_size_ceiling,
    _item_deletes_target_file,
    _split_plan_by_phase,
    TIER4_MAX_CONTEXT_CHARS,
    breakdown_plan,
)


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

    def _write_large_file(self, path: Path, size: int) -> None:
        with open(path, "w") as f:
            f.write("a" * size)

    def test_enforce_file_size_ceiling_does_not_block_fully_broken_down_state(self):
        self._write_large_file(self.target_path, TIER4_MAX_CONTEXT_CHARS + 1000)
        state = {
            "plan_text": "# Phase\n- [ ] Edit test_file.cpp to add a new method.",
            # project_dir is part of the persisted run state and is required by
            # breakdown_plan to resolve target paths.
            "project_dir": str(self.repo_root),
            "breakdown": {
                "phases": [
                    {
                        "name": "p",
                        "items": [
                            {
                                "target": "test_file.cpp",
                                "description": "Edit test_file.cpp to add a new method.",
                            }
                        ],
                    }
                ],
            },
        }
        phases = state["breakdown"]["phases"]
        self.assertEqual(len(phases), len(_split_plan_by_phase(state["plan_text"])))

        # Already fully broken down: no fresh chunk-to-phase assembly happens,
        # so the ceiling guard must not run at all (not even to re-mark a
        # stored item). Patching it to fail proves the already-broken-down
        # path never consults it.
        with mock.patch(
            "scripts.dispatcher._enforce_file_size_ceiling",
            side_effect=AssertionError(
                "ceiling guard must not run on an existing breakdown"
            ),
        ) as ceiling:
            result = breakdown_plan(state)
        self.assertEqual(result, {"status": "ok"})
        ceiling.assert_not_called()
        stored_item = state["breakdown"]["phases"][0]["items"][0]
        self.assertNotIn("skip_tier4", stored_item)

    def test_enforce_file_size_ceiling_still_fires_on_initial_breakdown(self):
        self._write_large_file(self.target_path, TIER4_MAX_CONTEXT_CHARS + 1000)
        state = {
            "plan_text": "# Phase\n- [ ] Edit test_file.cpp to add a new method.",
            "project_dir": str(self.repo_root),
            "breakdown": None,
        }
        phases = [
            {
                "name": "p",
                "items": [
                    {
                        "target": "test_file.cpp",
                        "description": "Edit test_file.cpp to add a new method.",
                    }
                ],
            }
        ]
        self.assertEqual(len(phases), len(_split_plan_by_phase(state["plan_text"])))

        # Fresh initial breakdown: the guard must still fire. It reports
        # success by returning None; firing is observable through the
        # skip_tier4 marker on the oversized item, not through a non-None
        # return value.
        result = _enforce_file_size_ceiling(phases, state["project_dir"])
        self.assertIsNone(result)
        item = phases[0]["items"][0]
        self.assertTrue(item["skip_tier4"])
        self.assertIn("test_file.cpp", item["description"])
        self.assertIn(str(TIER4_MAX_CONTEXT_CHARS + 1000), item["description"])
        self.assertIn("split it into cohesive smaller files", item["description"])

    def _task_id(self, name: str) -> str:
        self.task_ids.append(name)
        clear_state(name)
        return name

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

    def _phases_with_desc(self, target: str, description: str) -> list[dict]:
        return [{"name": "p", "items": [{"target": target, "description": description}]}]

    def test_enforce_file_size_ceiling_marks_skip_tier4_for_existing_large_file(self):
        self._write_large_file(self.target_path, TIER4_MAX_CONTEXT_CHARS + 1000)
        phases = self._phases_with_desc("test_file.cpp", "Edit test_file.cpp to add a new method.")
        result = _enforce_file_size_ceiling(phases, str(self.repo_root))
        self.assertIsNone(result)
        item = phases[0]["items"][0]
        self.assertTrue(item["skip_tier4"])
        self.assertIn("test_file.cpp", item["description"])
        self.assertIn(str(TIER4_MAX_CONTEXT_CHARS + 1000), item["description"])
        self.assertIn("split it into cohesive smaller files", item["description"])

    def test_enforce_file_size_ceiling_ignores_small_existing_file(self):
        self._write_large_file(self.target_path, TIER4_MAX_CONTEXT_CHARS - 1000)
        result = _enforce_file_size_ceiling(self._phases("test_file.cpp"), str(self.repo_root))
        self.assertIsNone(result)

    def test_enforce_file_size_ceiling_ignores_nonexistent_file(self):
        result = _enforce_file_size_ceiling(self._phases("nonexistent_file.cpp"), str(self.repo_root))
        self.assertIsNone(result)

    def test_enforce_file_size_ceiling_exempts_deletion_of_oversized_file(self):
        # A package-split plan's retirement step must be able to delete the
        # very file whose size tripped the guard -- otherwise the fix for
        # an oversized file could never be dispatched.
        self._write_large_file(self.target_path, TIER4_MAX_CONTEXT_CHARS + 1000)
        phases = self._phases_with_desc(
            "test_file.cpp",
            "Delete the old test_file.cpp file once the package replaces it.",
        )
        result = _enforce_file_size_ceiling(phases, str(self.repo_root))
        self.assertIsNone(result)

    def test_enforce_file_size_ceiling_does_not_mark_deletion_item(self):
        # A deletion item on an oversized file is exempt outright -- it
        # doesn't need Tier 3/2 routing at all (verify_only items never
        # reach run_task/Tier 4 in the first place), and marking it would
        # be meaningless since there's no content left to shrink.
        self._write_large_file(self.target_path, TIER4_MAX_CONTEXT_CHARS + 1000)
        phases = self._phases_with_desc(
            "test_file.cpp",
            "Delete the old test_file.cpp file once the package replaces it.",
        )
        result = _enforce_file_size_ceiling(phases, str(self.repo_root))
        self.assertIsNone(result)
        self.assertNotIn("skip_tier4", phases[0]["items"][0])

    def test_item_deletes_target_file_requires_verb_near_filename(self):
        deletes = {
            "target": "ohmyllama/state.py",
            "description": "Delete the old ohmyllama/state.py file once the package replaces it.",
        }
        edits = {
            "target": "ohmyllama/state.py",
            "description": "Edit ohmyllama/state.py to add a new method.",
        }
        far_mention = {
            "target": "ohmyllama/state.py",
            "description": (
                "Delete the stale cache directory. " + ("x" * 200) +
                " Separately, also touch ohmyllama/state.py."
            ),
        }
        self.assertTrue(_item_deletes_target_file(deletes))
        self.assertFalse(_item_deletes_target_file(edits))
        self.assertFalse(_item_deletes_target_file(far_mention))

    def test_item_deletes_target_file_rejects_delete_of_content_within_file(self):
        """Real incident 2026-08-20: a plan item pruning stale sections OUT
        of AGENTS.md (not deleting AGENTS.md itself) false-positive-matched
        the old 80-char-proximity check because "delete" and "AGENTS.md"
        both appeared in the same sentence, letting an oversized file skip
        the size-ceiling guard and go to Tier 4 undefended."""
        prune_content = {
            "target": "AGENTS.md",
            "description": (
                "Prune fully-superseded/never-dispatched blocks from `AGENTS.md`: "
                "delete everything between and including the start/end markers."
            ),
        }
        self.assertFalse(_item_deletes_target_file(prune_content))

    def test_item_deletes_target_file_matches_path_prefixed_mention(self):
        deletes_with_path = {
            "target": "ohmyllama/webui.py",
            "description": "Finalize the deletion: run `git rm ohmyllama/webui.py` to remove ohmyllama/webui.py for good.",
        }
        self.assertTrue(_item_deletes_target_file(deletes_with_path))

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
