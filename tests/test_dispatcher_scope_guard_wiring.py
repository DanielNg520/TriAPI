import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from scripts import dispatcher

_OUT_OF_SCOPE_DIFF = """\
diff --git a/scripts/llm_client.py b/scripts/llm_client.py
index 1111111..2222222 100644
--- a/scripts/llm_client.py
+++ b/scripts/llm_client.py
@@ -185,6 +185,7 @@ def _call_claude_cli(
     prompt: str, system_prompt: str, model: str | None = None, effort: str | None = None
 ) -> Tuple[str, str, int, int]:
+    prompt = prompt.strip()
     cmd = ["claude", "-p", "--system-prompt", system_prompt]
@@ -206,6 +207,10 @@ def _call_agy_cli(
     prompt: str, model: str | None, effort: str | None, system_prompt: str | None = None
 ) -> Tuple[str, str, int, int]:
+    if len(prompt) > _AGY_MAX_PROMPT_CHARS:
+        raise subprocess.CalledProcessError(0, [], "", "too long")
     if system_prompt:
         prompt = f"{system_prompt}\\n\\n{prompt}"
     cmd = ["agy", "-p", prompt]
"""

_JUDGE_APPROVED = {"status": "ok", "approved": True, "reason": "looks good", "cost_usd": 0.0}


class TestDispatcherScopeGuardWiring(unittest.TestCase):
    """Integration coverage for dispatcher.dispatch() wiring
    scope_guard.find_out_of_scope_functions() into each successful
    regular item's result entry (queue item, 2026-08-28: Tier 3
    out-of-scope-edit pattern), the same non-blocking-flag pattern
    mock_patch_lint's test-file findings already use in this loop.

    The design judge (scripts.judge) is mocked approved=True throughout --
    it's a separate, unrelated advisory gate this test isn't targeting,
    and leaving it live would exercise handle_fix_forward()'s real Tier 3
    escalation path via unmocked subprocess calls."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.project_dir = self.tmpdir.name
        self.target_file = Path(self.project_dir) / "target.py"
        self.target_file.write_text("original content\n", encoding="utf-8")

    def tearDown(self):
        self.tmpdir.cleanup()

    def _state(self, description):
        return {
            "run_id": "run-test",
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
                                "build_cmd": "echo built",
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
    @mock.patch("scripts.judge.evaluate_design", return_value=_JUDGE_APPROVED)
    @mock.patch("scripts.judge.extract_pattern")
    @mock.patch("subprocess.run")
    def test_out_of_scope_diff_flags_scope_concerns_on_entry(
        self, mock_run, mock_extract, mock_eval, mock_run_task, mock_check_ok, mock_save
    ):
        mock_run_task.return_value = {"status": "success", "resolved_by": "tier_3"}
        mock_run.return_value = SimpleNamespace(returncode=0, stdout=_OUT_OF_SCOPE_DIFF, stderr="")

        state = self._state("Fix the argv-length crash in _call_agy_cli()")
        result_state = dispatcher.dispatch(state)

        entry = result_state["results"][0]
        self.assertEqual(entry.get("scope_concerns"), ["_call_claude_cli"])

    @mock.patch("scripts.dispatcher.save_run")
    @mock.patch("scripts.dispatcher.check_tier2_ok", return_value={"ok": True})
    @mock.patch("scripts.dispatcher.run_task")
    @mock.patch("scripts.judge.evaluate_design", return_value=_JUDGE_APPROVED)
    @mock.patch("scripts.judge.extract_pattern")
    @mock.patch("subprocess.run")
    def test_in_scope_diff_does_not_set_scope_concerns(
        self, mock_run, mock_extract, mock_eval, mock_run_task, mock_check_ok, mock_save
    ):
        mock_run_task.return_value = {"status": "success", "resolved_by": "tier_3"}
        mock_run.return_value = SimpleNamespace(returncode=0, stdout=_OUT_OF_SCOPE_DIFF, stderr="")

        # Description names BOTH actually-touched functions -- not flagged.
        state = self._state("Fix a bug in _call_claude_cli() and _call_agy_cli()")
        result_state = dispatcher.dispatch(state)

        entry = result_state["results"][0]
        self.assertNotIn("scope_concerns", entry)

    @mock.patch("scripts.dispatcher.save_run")
    @mock.patch("scripts.dispatcher.check_tier2_ok", return_value={"ok": True})
    @mock.patch("scripts.dispatcher.run_task")
    @mock.patch("scripts.judge.evaluate_design", return_value=_JUDGE_APPROVED)
    @mock.patch("scripts.judge.extract_pattern")
    @mock.patch("subprocess.run")
    def test_scope_concerns_does_not_block_dispatch(
        self, mock_run, mock_extract, mock_eval, mock_run_task, mock_check_ok, mock_save
    ):
        # A flagged item must still be reported as a normal success --
        # this is advisory, never a hard block.
        mock_run_task.return_value = {"status": "success", "resolved_by": "tier_3"}
        mock_run.return_value = SimpleNamespace(returncode=0, stdout=_OUT_OF_SCOPE_DIFF, stderr="")

        state = self._state("Fix the argv-length crash in _call_agy_cli()")
        result_state = dispatcher.dispatch(state)

        self.assertEqual(result_state["results"][0]["status"], "success")
        self.assertNotEqual(result_state["status"], "stopped_on_failure")


if __name__ == "__main__":
    unittest.main()
