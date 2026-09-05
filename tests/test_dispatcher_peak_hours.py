"""Regression tests for dispatcher._is_deepseek_peak_hours() delegation."""

from __future__ import annotations

import unittest
from unittest import mock

from scripts import budget_guard, dispatcher, dispatcher_breakdown


class IsDeepseekPeakHoursTests(unittest.TestCase):
    """Verify dispatcher._is_deepseek_peak_hours() delegates to
    budget_guard.check_tier3_peak_hours_ok() instead of hardcoding logic."""

    def test_weekend_case_returns_false(self) -> None:
        """When budget_guard says peak hours are OK (e.g. weekend),
        _is_deepseek_peak_hours() must return False."""
        with mock.patch.object(
            dispatcher,
            "check_tier3_peak_hours_ok",
            return_value={"ok": True},
        ) as mock_check:
            result = dispatcher._is_deepseek_peak_hours()

        self.assertFalse(result)
        mock_check.assert_called_once()

    def test_peak_window_case_returns_true(self) -> None:
        """When budget_guard says peak hours are NOT OK (e.g. peak window),
        _is_deepseek_peak_hours() must return True."""
        with mock.patch.object(
            dispatcher,
            "check_tier3_peak_hours_ok",
            return_value={"ok": False},
        ) as mock_check:
            result = dispatcher._is_deepseek_peak_hours()

        self.assertTrue(result)
        mock_check.assert_called_once()

    def test_mock_was_actually_called(self) -> None:
        """Assert the delegation mock was invoked (covers all branches)."""
        with mock.patch.object(
            dispatcher,
            "check_tier3_peak_hours_ok",
            return_value={"ok": True},
        ) as mock_check:
            dispatcher._is_deepseek_peak_hours()

        self.assertTrue(mock_check.called)
        self.assertEqual(mock_check.call_count, 1)


class BreakdownPhaseResolvesPeakConditionalTests(unittest.TestCase):
    """breakdown_phase() must resolve tier_2_manager's peak_alt block like
    every other real Tier 2 call site (e.g. tier2_escalate.py) does,
    instead of always using the raw off-peak block regardless of the
    actual DeepSeek billing window."""

    def _config(self):
        return {
            "tier_2_manager": {
                "provider": "deepseek",
                "endpoint": "https://api.deepseek.com",
                "models": {"default": "deepseek-v4-pro"},
                "default_model": "default",
                "api_key_secret": "deepseek_api_key",
                "peak_alt": {
                    "provider": "agy",
                    "models": {"default": "gemini-3.1-pro"},
                    "default_model": "default",
                },
            }
        }

    def test_off_peak_uses_primary_block(self) -> None:
        with (
            mock.patch.object(dispatcher_breakdown, "load_tiers", return_value=self._config()),
            mock.patch.object(dispatcher_breakdown, "load_secrets", return_value={}),
            mock.patch.object(dispatcher_breakdown, "check_tier2_ok", return_value={"ok": True}),
            mock.patch.object(
                budget_guard, "check_tier3_peak_hours_ok", return_value={"ok": True}
            ),
            mock.patch.object(
                dispatcher_breakdown,
                "_breakdown_phase_attempt",
                return_value={"status": "ok", "phase": {"name": "p", "items": []}},
            ) as mock_attempt,
        ):
            dispatcher_breakdown.breakdown_phase("some phase text")

        used_tier2 = mock_attempt.call_args[0][2]
        self.assertEqual(used_tier2["provider"], "deepseek")

    def test_peak_hours_resolves_to_peak_alt_block(self) -> None:
        with (
            mock.patch.object(dispatcher_breakdown, "load_tiers", return_value=self._config()),
            mock.patch.object(dispatcher_breakdown, "load_secrets", return_value={}),
            mock.patch.object(dispatcher_breakdown, "check_tier2_ok", return_value={"ok": True}),
            mock.patch.object(
                budget_guard, "check_tier3_peak_hours_ok", return_value={"ok": False}
            ),
            mock.patch.object(
                dispatcher_breakdown,
                "_breakdown_phase_attempt",
                return_value={"status": "ok", "phase": {"name": "p", "items": []}},
            ) as mock_attempt,
        ):
            dispatcher_breakdown.breakdown_phase("some phase text")

        used_tier2 = mock_attempt.call_args[0][2]
        self.assertEqual(used_tier2["provider"], "agy")


class BreakdownPhaseAttemptAgyNoEndpointTests(unittest.TestCase):
    """Real incident 2026-09-02: during DeepSeek's peak window,
    breakdown_phase() correctly resolves tier_2_manager's peak_alt block
    (provider: agy, no 'endpoint' key -- same shape as every other
    agy-provider tier block in this repo), but _breakdown_phase_attempt()
    did a strict tier2["endpoint"] subscript and crashed with
    KeyError: 'endpoint' the first time a real breakdown ran during peak
    hours, instead of degrading to None like every other agy call site
    (tier2_escalate.py, tier3_escalate.py both already use .get())."""

    def test_agy_block_with_no_endpoint_key_does_not_raise(self) -> None:
        from scripts.dispatcher_breakdown import _breakdown_phase_attempt

        tier2 = {"provider": "agy", "models": {"default": "gemini-3.1-pro"}}
        with mock.patch(
            "scripts.llm_client.execute_llm",
            return_value=('{"name": "Phase 1", "items": []}', "agy", 0, 0),
        ) as mock_execute:
            result = _breakdown_phase_attempt("some phase text", ["gemini-3.1-pro"], tier2, {})

        self.assertEqual(result["status"], "ok")
        self.assertIsNone(mock_execute.call_args.kwargs["endpoint"])

    def test_effort_is_threaded_through_to_execute_llm(self) -> None:
        """Real incident 2026-09-02, found immediately after the endpoint
        fix above: the live `agy` CLI rejects `--model gemini-3.1-pro` with
        no `--effort` at all ("requires --effort"), but
        _breakdown_phase_attempt() never read tier2.get("effort") -- every
        other real agy call site in this repo (tier2_escalate.py,
        tier3_escalate.py) already threads it through."""
        from scripts.dispatcher_breakdown import _breakdown_phase_attempt

        tier2 = {"provider": "agy", "models": {"default": "gemini-3.1-pro"}, "effort": "high"}
        with mock.patch(
            "scripts.llm_client.execute_llm",
            return_value=('{"name": "Phase 1", "items": []}', "agy", 0, 0),
        ) as mock_execute:
            _breakdown_phase_attempt("some phase text", ["gemini-3.1-pro"], tier2, {})

        self.assertEqual(mock_execute.call_args.kwargs["effort"], "high")


if __name__ == "__main__":
    unittest.main()
