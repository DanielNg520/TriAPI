"""Regression tests for tier reassignment prep features.

Zero-network tests using unittest and unittest.mock.
"""

from __future__ import annotations

import json
import subprocess
import time
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import mock

from scripts import budget_guard, dispatcher, gemini_fallback, llm_client


def _make_config(tier_deepseek, tier_google, deepseek_peak=None):
    """Helper to build a minimal tiers config dict as returned by
    config_loader.load_tiers() -- tier blocks live directly at the top level
    (keyed by tier name), not nested under a "tiers" key or a "providers"
    sub-dict. Matches what budget_guard.resolve_deepseek_tier() and
    check_tier3_peak_hours_ok() actually expect."""
    config = {}
    if tier_deepseek:
        block = {"provider": "deepseek", "endpoint": budget_guard.DEEPSEEK_ENDPOINT}
        if deepseek_peak is not None:
            block["peak_hours_utc"] = deepseek_peak
        config[tier_deepseek] = block
    if tier_google:
        config.setdefault(
            tier_google, {"provider": "google", "endpoint": "https://gemini.googleapis.com"}
        )
    return config


def _fixed_datetime(fixed):
    """Build a datetime subclass whose now() always returns `fixed`
    (converted to the requested tz), for patching budget_guard's module-level
    `datetime` name -- the real check_tier3_peak_hours_ok() reads the clock
    via datetime.now(timezone.utc), not time.time()."""

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed.astimezone(tz) if tz else fixed

    return _FixedDateTime


class TestAgyProviderSuccess(unittest.TestCase):
    def test_execute_llm_agy_success(self):
        prompt = "hello"
        expected_argv = [
            "agy", "-p", prompt,
            "--model", "m",
            "--effort", "high",
            "--dangerously-skip-permissions",
            "--output-format", "json",
        ]
        stdout_json = json.dumps({"status": "SUCCESS", "response": "pong\n"})
        mock_result = SimpleNamespace(returncode=0, stdout=stdout_json, stderr="")
        with mock.patch.object(llm_client.subprocess, "run", return_value=mock_result) as mock_run:
            result = llm_client.execute_llm(
                provider="agy", endpoint="", api_key="", model="m",
                prompt=prompt, system_prompt="", effort="high"
            )
        self.assertEqual(result, ("pong\n", "agy", 0, 0))
        mock_run.assert_called_once()
        actual_argv = mock_run.call_args[0][0]
        self.assertEqual(actual_argv, expected_argv)


class TestAgyProviderGracefulFailure(unittest.TestCase):
    def test_nonzero_returncode_raises_calledprocesserror(self):
        mock_result = SimpleNamespace(returncode=1, stdout="", stderr="some error")
        with mock.patch.object(llm_client.subprocess, "run", return_value=mock_result):
            with self.assertRaises(subprocess.CalledProcessError):
                llm_client.execute_llm(
                    provider="agy", endpoint="", api_key="", model="m",
                    prompt="test", system_prompt="", effort="high"
                )

    def test_undecodable_stdout_raises_calledprocesserror(self):
        mock_result = SimpleNamespace(returncode=0, stdout="not json", stderr="")
        with mock.patch.object(llm_client.subprocess, "run", return_value=mock_result):
            with self.assertRaises(subprocess.CalledProcessError):
                llm_client.execute_llm(
                    provider="agy", endpoint="", api_key="", model="m",
                    prompt="test", system_prompt="", effort="high"
                )

    def test_non_success_status_raises_calledprocesserror(self):
        stdout_json = json.dumps({"status": "QUOTA_EXCEEDED", "response": ""})
        mock_result = SimpleNamespace(returncode=0, stdout=stdout_json, stderr="")
        with mock.patch.object(llm_client.subprocess, "run", return_value=mock_result):
            with self.assertRaises(subprocess.CalledProcessError):
                llm_client.execute_llm(
                    provider="agy", endpoint="", api_key="", model="m",
                    prompt="test", system_prompt="", effort="high"
                )

    def test_non_string_response_raises_calledprocesserror(self):
        stdout_json = json.dumps({"status": "SUCCESS", "response": 123})
        mock_result = SimpleNamespace(returncode=0, stdout=stdout_json, stderr="")
        with mock.patch.object(llm_client.subprocess, "run", return_value=mock_result):
            with self.assertRaises(subprocess.CalledProcessError):
                llm_client.execute_llm(
                    provider="agy", endpoint="", api_key="", model="m",
                    prompt="test", system_prompt="", effort="high"
                )


class TestBreakdownPhaseAttemptRouting(unittest.TestCase):
    def test_routing_for_non_google_providers(self):
        # _breakdown_phase_attempt's non-google branch does
        # `from scripts.llm_client import execute_llm` *inside* the function
        # body on every call, so the patch target must be the real owning
        # module (scripts.llm_client), not an attribute dispatcher never
        # binds at import time.
        providers = ["deepseek", "cli", "agy", "openrouter"]
        for provider in providers:
            with self.subTest(provider=provider):
                tier2 = {
                    "provider": provider,
                    "endpoint": "http://example.test",
                    "api_key_secret": "some_key",
                }
                secrets = {"some_key": "secret-value"}
                with (
                    mock.patch(
                        "scripts.llm_client.execute_llm",
                        return_value=('{"name": "p", "items": []}', provider, 0, 0),
                    ) as mock_execute,
                    mock.patch(
                        "scripts.dispatcher.gemini_fallback.post_generate_content"
                    ) as mock_post,
                ):
                    dispatcher._breakdown_phase_attempt(
                        phase_text="test", models=["m"], tier2=tier2, secrets=secrets
                    )
                    mock_execute.assert_called_once()
                    mock_post.assert_not_called()

    def test_routing_for_google_provider(self):
        tier2 = {
            "provider": "google",
            "endpoint": "http://example.test",
            "api_key_secret": "some_key",
        }
        secrets = {"some_key": "secret-value"}
        resp = mock.Mock()
        resp.raise_for_status = mock.Mock()
        resp.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": '{"name": "p", "items": []}'}]}}]
        }
        with (
            mock.patch("scripts.llm_client.execute_llm") as mock_execute,
            mock.patch(
                "scripts.dispatcher.gemini_fallback.post_generate_content",
                return_value=(resp, "model-a"),
            ) as mock_post,
        ):
            dispatcher._breakdown_phase_attempt(
                phase_text="test", models=["model-a"], tier2=tier2, secrets=secrets
            )
            mock_execute.assert_not_called()
            mock_post.assert_called_once()


class TestPeakHoursPositionIndependence(unittest.TestCase):
    def test_resolve_deepseek_tier_position_independent(self):
        # resolve_deepseek_tier scans a fixed TIER_SCAN_ORDER for whichever
        # tier block has provider == "deepseek" -- it must find the deepseek
        # tier regardless of which tier name (tier_2_manager vs
        # tier_3_debugger) actually hosts it.
        config_a = _make_config(
            tier_deepseek="tier_3_debugger",
            tier_google="tier_2_manager",
            deepseek_peak=[["06:00", "10:00"]],
        )
        config_b = _make_config(
            tier_deepseek="tier_2_manager",
            tier_google="tier_3_debugger",
            deepseek_peak=[["22:00", "23:00"]],
        )
        self.assertEqual(budget_guard.resolve_deepseek_tier(config_a), "tier_3_debugger")
        self.assertEqual(budget_guard.resolve_deepseek_tier(config_b), "tier_2_manager")

    def test_peak_hours_gating_position_independent(self):
        # All three fixed times below fall on UTC weekdays in both the UTC
        # and Asia/Shanghai calendars, so check_tier3_peak_hours_ok's
        # weekend off-peak bypass never triggers.
        config_a = _make_config(
            tier_deepseek="tier_3_debugger",
            tier_google="tier_2_manager",
            deepseek_peak=[["06:00", "10:00"]],
        )
        config_b = _make_config(
            tier_deepseek="tier_2_manager",
            tier_google="tier_3_debugger",
            deepseek_peak=[["22:00", "23:00"]],
        )
        time_in_a_window = datetime(2026, 1, 5, 8, 0, tzinfo=timezone.utc)
        time_in_b_window = datetime(2026, 1, 5, 22, 30, tzinfo=timezone.utc)
        time_outside_both = datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc)

        with mock.patch.object(budget_guard, "datetime", _fixed_datetime(time_in_a_window)):
            with mock.patch.object(budget_guard, "load_tiers", return_value=config_a):
                self.assertFalse(budget_guard.check_tier3_peak_hours_ok()["ok"])
            with mock.patch.object(budget_guard, "load_tiers", return_value=config_b):
                self.assertTrue(budget_guard.check_tier3_peak_hours_ok()["ok"])

        with mock.patch.object(budget_guard, "datetime", _fixed_datetime(time_in_b_window)):
            with mock.patch.object(budget_guard, "load_tiers", return_value=config_a):
                self.assertTrue(budget_guard.check_tier3_peak_hours_ok()["ok"])
            with mock.patch.object(budget_guard, "load_tiers", return_value=config_b):
                self.assertFalse(budget_guard.check_tier3_peak_hours_ok()["ok"])

        with mock.patch.object(budget_guard, "datetime", _fixed_datetime(time_outside_both)):
            with mock.patch.object(budget_guard, "load_tiers", return_value=config_a):
                self.assertTrue(budget_guard.check_tier3_peak_hours_ok()["ok"])
            with mock.patch.object(budget_guard, "load_tiers", return_value=config_b):
                self.assertTrue(budget_guard.check_tier3_peak_hours_ok()["ok"])

    def test_no_deepseek_returns_none_and_default_peak_hours(self):
        config_c = _make_config(tier_deepseek=None, tier_google="tier_2_manager")
        self.assertIsNone(budget_guard.resolve_deepseek_tier(config_c))
        # 08:00 UTC on a weekday falls inside the default peak window
        # (06:00-10:00 UTC) that applies when no deepseek tier resolves.
        fixed = datetime(2026, 1, 5, 8, 0, tzinfo=timezone.utc)
        with (
            mock.patch.object(budget_guard, "load_tiers", return_value=config_c),
            mock.patch.object(budget_guard, "datetime", _fixed_datetime(fixed)),
        ):
            result = budget_guard.check_tier3_peak_hours_ok()
        self.assertFalse(result["ok"])


class TestDispatcherAdvisoryDelegation(unittest.TestCase):
    def test_is_deepseek_peak_hours_true_despite_check_tier3_false(self):
        # dispatcher._is_deepseek_peak_hours() takes no meaningful config;
        # it purely delegates to budget_guard.check_tier3_peak_hours_ok()
        # (imported by name into scripts.dispatcher) and inverts its "ok"
        # field. check_tier3_peak_hours_ok() returns a dict, not a bare
        # bool -- "ok": False means "in peak hours", so the delegating call
        # must report True.
        with mock.patch.object(
            dispatcher,
            "check_tier3_peak_hours_ok",
            return_value={"ok": False, "reason": "DeepSeek peak hours active"},
        ) as mock_check:
            result = dispatcher._is_deepseek_peak_hours()
        mock_check.assert_called_once_with()
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
