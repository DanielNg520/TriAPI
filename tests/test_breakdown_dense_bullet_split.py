"""Regression tests for dispatcher_breakdown._split_phase_by_dense_bullet() /
breakdown_phase()'s dense-bullet split.

Real incident (2026-09-01/02): a single unusually long/dense checklist
bullet lost most of its technical detail during Tier 2/Gemini
phase-breakdown compression when batched into the same call as several
other, much shorter bullets -- despite BREAKDOWN_SYSTEM_INSTRUCTION's
explicit "carry forward every concrete technical requirement... failure to
do so" instruction. This guards the fix: a bullet whose own text clearly
dominates the phase gets split off into its own breakdown_phase() call.
"""

from __future__ import annotations

import unittest
from unittest import mock

from scripts import dispatcher_breakdown


class SplitPhaseByDenseBulletTests(unittest.TestCase):
    def test_no_split_when_bullets_are_similar_size(self) -> None:
        phase_text = (
            "## Phase 1 -- do things\n"
            "- [ ] **a.py** -- do a short thing.\n"
            "- [ ] **b.py** -- do another short thing.\n"
            "- [ ] **c.py** -- do a third short thing.\n"
        )
        self.assertIsNone(dispatcher_breakdown._split_phase_by_dense_bullet(phase_text))

    def test_no_split_with_only_one_bullet(self) -> None:
        phase_text = "## Phase 1 -- do things\n" + ("- [ ] **a.py** -- " + "x" * 5000 + "\n")
        # Only one bullet total -- nothing to split it off from.
        self.assertIsNone(dispatcher_breakdown._split_phase_by_dense_bullet(phase_text))

    def test_splits_off_dominant_bullet(self) -> None:
        header = "## Phase 1 -- do things\n"
        small_bullet = "- [ ] **a.py** -- do a short thing.\n"
        dense_bullet = "- [ ] **b.py** -- " + ("detail " * 1000) + "\n"
        phase_text = header + small_bullet + dense_bullet

        result = dispatcher_breakdown._split_phase_by_dense_bullet(phase_text)
        self.assertIsNotNone(result)
        rest_text, dense_text = result

        self.assertIn(header.strip(), rest_text)
        self.assertIn("a.py", rest_text)
        self.assertNotIn("detail detail", rest_text)

        self.assertIn(header.strip(), dense_text)
        self.assertIn("b.py", dense_text)
        self.assertNotIn("a.py", dense_text)

    def test_no_split_below_threshold(self) -> None:
        header = "## Phase 1 -- do things\n"
        small_bullet = "- [ ] **a.py** -- do a short thing.\n"
        # Bigger than small_bullet but well under the absolute threshold.
        medium_bullet = "- [ ] **b.py** -- " + ("detail " * 50) + "\n"
        phase_text = header + small_bullet + medium_bullet
        self.assertIsNone(dispatcher_breakdown._split_phase_by_dense_bullet(phase_text))


class BreakdownPhaseDenseSplitIntegrationTests(unittest.TestCase):
    def _config(self):
        return {
            "tier_2_manager": {
                "provider": "deepseek",
                "endpoint": "https://api.deepseek.com",
                "models": {"default": "deepseek-v4-pro"},
                "default_model": "default",
                "api_key_secret": "deepseek_api_key",
            }
        }

    def test_dense_phase_makes_two_calls_and_merges_items(self) -> None:
        header = "## Phase 1 -- do things\n"
        small_bullet = "- [ ] **a.py** -- do a short thing.\n"
        dense_bullet = "- [ ] **b.py** -- " + ("detail " * 1000) + "\n"
        phase_text = header + small_bullet + dense_bullet

        def fake_attempt(text, models, tier2, secrets):
            if "detail detail" in text:
                return {"status": "ok", "phase": {"name": "Phase 1", "items": [{"target": "b.py"}]}}
            return {"status": "ok", "phase": {"name": "Phase 1", "items": [{"target": "a.py"}]}}

        with (
            mock.patch.object(dispatcher_breakdown, "load_tiers", return_value=self._config()),
            mock.patch.object(dispatcher_breakdown, "load_secrets", return_value={}),
            mock.patch.object(dispatcher_breakdown, "check_tier2_ok", return_value={"ok": True}),
            mock.patch.object(dispatcher_breakdown, "_breakdown_phase_attempt", side_effect=fake_attempt) as mock_attempt,
        ):
            result = dispatcher_breakdown.breakdown_phase(phase_text)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(mock_attempt.call_count, 2)
        targets = {item["target"] for item in result["phase"]["items"]}
        self.assertEqual(targets, {"a.py", "b.py"})

    def test_non_dense_phase_makes_one_call(self) -> None:
        phase_text = (
            "## Phase 1 -- do things\n"
            "- [ ] **a.py** -- do a short thing.\n"
            "- [ ] **b.py** -- do another short thing.\n"
        )
        with (
            mock.patch.object(dispatcher_breakdown, "load_tiers", return_value=self._config()),
            mock.patch.object(dispatcher_breakdown, "load_secrets", return_value={}),
            mock.patch.object(dispatcher_breakdown, "check_tier2_ok", return_value={"ok": True}),
            mock.patch.object(
                dispatcher_breakdown,
                "_breakdown_phase_attempt",
                return_value={"status": "ok", "phase": {"name": "Phase 1", "items": [{"target": "a.py"}, {"target": "b.py"}]}},
            ) as mock_attempt,
        ):
            result = dispatcher_breakdown.breakdown_phase(phase_text)

        self.assertEqual(result["status"], "ok")
        mock_attempt.assert_called_once()

    def test_rest_failure_short_circuits_before_dense_call(self) -> None:
        header = "## Phase 1 -- do things\n"
        small_bullet = "- [ ] **a.py** -- do a short thing.\n"
        dense_bullet = "- [ ] **b.py** -- " + ("detail " * 1000) + "\n"
        phase_text = header + small_bullet + dense_bullet

        with (
            mock.patch.object(dispatcher_breakdown, "load_tiers", return_value=self._config()),
            mock.patch.object(dispatcher_breakdown, "load_secrets", return_value={}),
            mock.patch.object(dispatcher_breakdown, "check_tier2_ok", return_value={"ok": True}),
            mock.patch.object(
                dispatcher_breakdown,
                "_breakdown_phase_attempt",
                return_value={"status": "error", "reason": "boom"},
            ) as mock_attempt,
        ):
            result = dispatcher_breakdown.breakdown_phase(phase_text, max_attempts=1)

        self.assertEqual(result["status"], "error")
        # Only the rest_text call happened -- the dense call is skipped
        # once the rest half has already failed.
        self.assertEqual(mock_attempt.call_count, 1)


if __name__ == "__main__":
    unittest.main()
