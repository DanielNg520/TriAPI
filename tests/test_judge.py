"""Tests for the design judge script."""

from __future__ import annotations

import fcntl
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import judge


class JudgeTests(unittest.TestCase):
    def setUp(self) -> None:
        # Mock load_tiers
        self.config_patcher = mock.patch("scripts.judge.load_tiers")
        self.mock_load_tiers = self.config_patcher.start()
        self.mock_load_tiers.return_value = {
            "tier_3_debugger": {
                "default_model": "deepseek-chat",
                "models": {"deepseek-chat": "deepseek-chat-v3"},
                "pricing": {"deepseek-chat": {"prompt_cache_hit_tokens": 0.0}},
                "endpoint": "https://api.deepseek.com",
                "api_key_secret": "deepseek_api_key",
            }
        }

        # Mock load_secrets
        self.secrets_patcher = mock.patch("scripts.judge.load_secrets")
        self.mock_load_secrets = self.secrets_patcher.start()
        self.mock_load_secrets.return_value = {"deepseek_api_key": "test_deepseek_key"}

        # Mock cost calculations
        self.compute_cost_patcher = mock.patch("scripts.judge.compute_cost")
        self.mock_compute_cost = self.compute_cost_patcher.start()
        self.mock_compute_cost.return_value = (0.0015, False)

        # Mock cost logging
        self.log_cost_patcher = mock.patch("scripts.judge.log_cost")
        self.mock_log_cost = self.log_cost_patcher.start()

    def tearDown(self) -> None:
        self.config_patcher.stop()
        self.secrets_patcher.stop()
        self.compute_cost_patcher.stop()
        self.log_cost_patcher.stop()

    def test_clean_response_variants(self) -> None:
        """Verify markdown cleanup for various formats."""
        # Standard markdown block with language tag
        self.assertEqual(
            judge.clean_response('```json\n{"approved": true}\n```'),
            '{"approved": true}',
        )
        # Fenced block without language tag
        self.assertEqual(
            judge.clean_response('```\n{"approved": false}\n```'),
            '{"approved": false}',
        )
        # No fencing at all
        self.assertEqual(
            judge.clean_response('{"approved": true}'),
            '{"approved": true}',
        )
        # Surrounding whitespace
        self.assertEqual(
            judge.clean_response('  \n```json\n{"approved": true}\n```\n  '),
            '{"approved": true}',
        )

    def _execute_llm_result(self, content: str, input_tokens: int = 1, output_tokens: int = 1):
        # judge._call_tier3_with_retries now routes through
        # llm_client.execute_llm() (generic provider dispatch) instead of a
        # hardcoded DeepSeek-shaped requests.post -- these tests mock that
        # call site instead, matching execute_llm's
        # (response_text, billing_type, input_tokens, output_tokens) return
        # shape. See the judge.py/tier3_escalate.py fix, 2026-08-25.
        return (content, "deepseek", input_tokens, output_tokens)

    def test_evaluate_design_approved(self) -> None:
        content = json.dumps({"approved": True, "reason": "looks good"})
        with (
            mock.patch(
                "scripts.judge.check_tier3_peak_hours_ok", return_value={"ok": True}
            ),
            mock.patch(
                "scripts.judge.llm_client.execute_llm",
                return_value=self._execute_llm_result(content),
            ),
        ):
            result = judge.evaluate_design("diff", "goal")
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["approved"])
        self.assertEqual(result["reason"], "looks good")

    def test_evaluate_design_rejected(self) -> None:
        content = json.dumps({"approved": False, "reason": "does not match goal"})
        with (
            mock.patch(
                "scripts.judge.check_tier3_peak_hours_ok", return_value={"ok": True}
            ),
            mock.patch(
                "scripts.judge.llm_client.execute_llm",
                return_value=self._execute_llm_result(content),
            ),
        ):
            result = judge.evaluate_design("diff", "goal")
        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["approved"])
        self.assertEqual(result["reason"], "does not match goal")

    def test_evaluate_design_markdown_fenced_response(self) -> None:
        content = '```json\n{"approved": true, "reason": "ok"}\n```'
        with (
            mock.patch(
                "scripts.judge.check_tier3_peak_hours_ok", return_value={"ok": True}
            ),
            mock.patch(
                "scripts.judge.llm_client.execute_llm",
                return_value=self._execute_llm_result(content),
            ),
        ):
            result = judge.evaluate_design("diff", "goal")
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["approved"])

    def test_evaluate_design_retries_then_succeeds(self) -> None:
        bad_result = self._execute_llm_result("not json")
        good_result = self._execute_llm_result(
            json.dumps({"approved": True, "reason": "ok"})
        )
        with (
            mock.patch(
                "scripts.judge.check_tier3_peak_hours_ok", return_value={"ok": True}
            ),
            mock.patch(
                "scripts.judge.llm_client.execute_llm",
                side_effect=[bad_result, good_result],
            ) as mock_execute,
        ):
            result = judge.evaluate_design("diff", "goal")
        self.assertEqual(mock_execute.call_count, 2)
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["approved"])

    def test_evaluate_design_dual_parse_failure(self) -> None:
        bad_result = self._execute_llm_result("not json at all")
        with (
            mock.patch(
                "scripts.judge.check_tier3_peak_hours_ok", return_value={"ok": True}
            ),
            mock.patch(
                "scripts.judge.llm_client.execute_llm",
                return_value=bad_result,
            ) as mock_execute,
        ):
            result = judge.evaluate_design("diff", "goal")
        self.assertEqual(mock_execute.call_count, 2)
        self.assertEqual(result["status"], "error")
        self.assertFalse(result["approved"])
        self.assertIn("Could not parse judge response after retry", result["reason"])

    def test_evaluate_design_request_exception(self) -> None:
        with (
            mock.patch(
                "scripts.judge.check_tier3_peak_hours_ok", return_value={"ok": True}
            ),
            mock.patch(
                "scripts.judge.llm_client.execute_llm",
                side_effect=RuntimeError("connection error"),
            ) as mock_execute,
        ):
            result = judge.evaluate_design("diff", "goal")
        self.assertEqual(mock_execute.call_count, 2)
        self.assertEqual(result["status"], "error")
        self.assertFalse(result["approved"])

    def test_evaluate_design_peak_hours_skip(self) -> None:
        with (
            mock.patch(
                "scripts.judge.check_tier3_peak_hours_ok",
                return_value={"ok": False, "reason": "peak hours"},
            ),
            mock.patch("scripts.judge.llm_client.execute_llm") as mock_execute,
        ):
            result = judge.evaluate_design("diff", "goal")
        mock_execute.assert_not_called()
        self.assertEqual(result["status"], "skipped")
        self.assertFalse(result["approved"])
        self.assertEqual(result["reason"], "peak hours")
        self.assertEqual(result["cost_usd"], 0.0)

    def test_evaluate_design_logs_cost_per_attempt(self) -> None:
        content = json.dumps({"approved": True, "reason": "ok"})
        with (
            mock.patch(
                "scripts.judge.check_tier3_peak_hours_ok", return_value={"ok": True}
            ),
            mock.patch(
                "scripts.judge.llm_client.execute_llm",
                return_value=self._execute_llm_result(content),
            ),
        ):
            judge.evaluate_design("diff", "goal")
        self.mock_log_cost.assert_called_once()
        logged = self.mock_log_cost.call_args.args[0]
        self.assertEqual(logged["tier"], "tier_3")
        self.assertEqual(logged["task_id"], "judge")

    def test_extract_pattern_peak_hours_skip(self) -> None:
        with (
            mock.patch(
                "scripts.judge.check_tier3_peak_hours_ok",
                return_value={"ok": False, "reason": "peak hours"},
            ),
            mock.patch("scripts.judge.llm_client.execute_llm") as mock_execute,
        ):
            judge.extract_pattern("full file", "diff")
        mock_execute.assert_not_called()

    def test_extract_pattern_writes_snippet(self) -> None:
        content = "<triapi_snippet>\n### Lesson\nbody\n</triapi_snippet>"
        with tempfile.TemporaryDirectory() as tmp:
            hivemind_path = Path(tmp) / "hivemind.md"
            with (
                mock.patch(
                    "scripts.judge.check_tier3_peak_hours_ok", return_value={"ok": True}
                ),
                mock.patch(
                    "scripts.judge.llm_client.execute_llm",
                    return_value=self._execute_llm_result(content),
                ),
                mock.patch("scripts.judge.Path", side_effect=lambda p: hivemind_path if p == "knowledge/hivemind.md" else Path(p)),
            ):
                judge.extract_pattern("full file", "diff")
            written = hivemind_path.read_text(encoding="utf-8")
        self.assertIn("### Lesson", written)
        self.assertIn("body", written)

    def test_extract_pattern_dual_parse_failure_logs_error(self) -> None:
        bad_result = self._execute_llm_result("no snippet tags here")
        with (
            mock.patch(
                "scripts.judge.check_tier3_peak_hours_ok", return_value={"ok": True}
            ),
            mock.patch(
                "scripts.judge.llm_client.execute_llm",
                return_value=bad_result,
            ) as mock_execute,
            mock.patch("scripts.judge.log") as mock_log,
        ):
            judge.extract_pattern("full file", "diff")
        self.assertEqual(mock_execute.call_count, 2)
        mock_log.error.assert_called_once()

    def test_extract_pattern_lock_contention_skips_lock_but_still_writes(self) -> None:
        content = "<triapi_snippet>\n### Lesson\nbody\n</triapi_snippet>"
        with tempfile.TemporaryDirectory() as tmp:
            hivemind_path = Path(tmp) / "hivemind.md"
            with (
                mock.patch(
                    "scripts.judge.check_tier3_peak_hours_ok", return_value={"ok": True}
                ),
                mock.patch(
                    "scripts.judge.llm_client.execute_llm",
                    return_value=self._execute_llm_result(content),
                ),
                mock.patch("scripts.judge.Path", side_effect=lambda p: hivemind_path if p == "knowledge/hivemind.md" else Path(p)),
                mock.patch(
                    "scripts.judge.fcntl.flock",
                    side_effect=BlockingIOError("locked"),
                ),
            ):
                judge.extract_pattern("full file", "diff")
            written = hivemind_path.read_text(encoding="utf-8")
        self.assertIn("### Lesson", written)


if __name__ == "__main__":
    unittest.main()
