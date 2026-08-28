import unittest

from scripts import dispatcher


class TestBreakdownPromptSkipGuidance(unittest.TestCase):
    """Regression coverage for queue item 4 (2026-08-28): the Tier 2
    breakdown system prompt must warn against a bare unanchored
    `grep -i 'skipped'` verify_command, which false-triggers on any test
    NAME containing the substring "skipped" (e.g.
    test_jules_test_skipped_when_budget_check_refuses) -- confirmed live
    causing a false human_handoff. This only checks the prompt text itself
    contains the guidance; it cannot verify the breakdown model actually
    follows it (that's a live-verification concern, not a unit test one)."""

    def test_prompt_warns_against_bare_skipped_grep(self):
        prompt = dispatcher.BREAKDOWN_SYSTEM_INSTRUCTION
        self.assertIn("skipped", prompt.lower())
        self.assertIn("bare substring", prompt.lower())
        # The anchored unittest syntax it should steer toward.
        self.assertIn("skipped=", prompt)


if __name__ == "__main__":
    unittest.main()
