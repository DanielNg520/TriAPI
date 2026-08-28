from unittest import TestCase

from scripts import planner


class TestDetectDegeneratePlan(TestCase):
    """Regression coverage for the plan-sanity-check gap (queue item 5,
    2026-08-28): triapi plan's planning turn previously had no sanity
    check on its own output before it was treated as approvable, so a
    truncated, hallucinated (fake tool-call markup), or degenerate
    self-repeating response could be auto-approved by a blind piped
    'approve'."""

    def test_normal_plan_has_no_concerns(self):
        text = (
            "1. Phase 1: Add Hello World\n"
            "- [ ] `scripts/triapi.py`: Insert `print(\"hello\")` at the top of "
            "main(). Verify with `python3 -m py_compile scripts/triapi.py`.\n"
        )
        self.assertEqual(planner.detect_degenerate_plan(text), [])

    def test_short_response_is_flagged(self):
        concerns = planner.detect_degenerate_plan("ok")
        self.assertTrue(any("short" in c for c in concerns))

    def test_fake_tool_call_markup_is_flagged(self):
        text = (
            "<dots_function_call>\n<invoke name=\"read_file\">\n"
            "<parameter name=\"file_path\">x</parameter>\n</invoke>\n</dots_function_call>"
        )
        concerns = planner.detect_degenerate_plan(text)
        self.assertTrue(any("tool-call markup" in c for c in concerns))

    def test_degenerate_repeating_lines_are_flagged(self):
        text = "\n".join(["- [ ] do the thing"] * 10)
        concerns = planner.detect_degenerate_plan(text)
        self.assertTrue(any("degenerate" in c for c in concerns))

    def test_normal_plan_with_repeated_checkbox_prefix_not_falsely_flagged(self):
        # Real plans legitimately have many "- [ ]" lines that share a
        # prefix but differ in content -- only near-identical FULL lines
        # should trip the guard.
        lines = [f"- [ ] scripts/file_{i}.py: do step {i} specifically" for i in range(10)]
        text = "\n".join(lines)
        self.assertEqual(planner.detect_degenerate_plan(text), [])
