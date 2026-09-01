"""Regression tests for the 2026-08-19 plan-completion integrity bug.

Covers scripts/dispatcher.py's _split_plan_by_phase (now also recognizing
numbered "N. Phase ..." top-level markers, not just ATX headers) and
scripts/agents_md_gate.py's mark_plan_complete (now refusing to blindly
check off AGENTS.md boxes when the breakdown captured fewer items than the
block declares). See CARRYOVER.md's "#1 IN QUEUE (URGENT...)" entry for the
real incident this closes: run 20260819-063339-9d23c7's plan used numbered
phase markers instead of ATX headers, collapsed into one chunk, and
silently dropped 3 of 4 phases while still being marked fully complete.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.dispatcher import _split_plan_by_phase
from scripts.agents_md_gate import mark_plan_complete


class PlanSplitAndCompletionGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temp_dir.name)
        self.ags_md_path = self.repo_root / "AGENTS.md"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write_ags_md(self, content: str) -> None:
        with open(self.ags_md_path, "w") as f:
            f.write(content)

    def test_numbered_phase_markers_split_into_multiple_chunks(self) -> None:
        plan_text = (
            "# Phase 1\n"
            "1. Task one\n"
            "2. Task two\n"
            "\n"
            "# Phase 2\n"
            "3. Task three\n"
            "4. Task four\n"
        )
        chunks = _split_plan_by_phase(plan_text)
        self.assertEqual(len(chunks), 2)

    def test_mixed_numbered_and_atx_headers_still_split_correctly(self) -> None:
        plan_text = (
            "## Phase 1 -- Setup\n"
            "- [ ] Task one\n"
            "2. Phase 2 -- Build\n"
            "- [ ] Task two\n"
        )
        chunks = _split_plan_by_phase(plan_text)
        self.assertEqual(len(chunks), 2)
        self.assertTrue(chunks[0].startswith("## Phase 1"))
        self.assertTrue(chunks[1].startswith("2. Phase 2"))

    def test_bold_wrapped_numbered_phase_markers_split_correctly(self) -> None:
        """Real incident 2026-08-20 (run 20260820-081806-d7c25f): a plan used
        '1. **Phase 1 -- ...**' (bold markdown around 'Phase'), which the
        original number+literal-'Phase' match didn't recognize, silently
        collapsing a 14-phase plan into a single chunk."""
        plan_text = (
            "1. **Phase 1 -- Setup**\n"
            "   - [ ] Task one\n"
            "2. **Phase 2 -- Build**\n"
            "   - [ ] Task two\n"
        )
        chunks = _split_plan_by_phase(plan_text)
        self.assertEqual(len(chunks), 2)
        self.assertTrue(chunks[0].startswith("1. **Phase 1"))
        self.assertTrue(chunks[1].startswith("2. **Phase 2"))

    def test_atx_header_only_plan_unchanged(self) -> None:
        plan_text = (
            "# Phase 1\n"
            "- [ ] Task one\n"
            "\n"
            "## Subphase A\n"
            "- [ ] Task two\n"
        )
        chunks = _split_plan_by_phase(plan_text)
        self.assertEqual(len(chunks), 2)

    def test_h1_title_with_rationale_bullets_dropped_before_real_phases(self) -> None:
        # Real incident, 2026-09-01 (run 20260901-135001-dd5f98): a plan's
        # own "# Execution Plan -- ..." H1 title followed by prose "Key
        # decisions" bullets (not real checklist items) matched the loose
        # bullet-based checklist filter and got dispatched as a bogus extra
        # phase, duplicating the real Phase 1 work before it even ran.
        plan_text = (
            "# Execution Plan — Retire `ohmyllama` imports\n"
            "\n"
            "Grounded by reading the current on-disk source.\n"
            "\n"
            "**Key decisions made while reading the code:**\n"
            "- `resolve_secret` -> new standalone `src/semai/security/secrets.py`.\n"
            "- `BrowserCapability` -> wholesale port to `src/semai/capabilities/browser.py`.\n"
            "\n"
            "## Phase 1 — Foundational ports\n"
            "- [ ] Create `src/semai/security/secrets.py`\n"
            "\n"
            "## Phase 2 — Repoint call sites\n"
            "- [ ] Edit `src/semai/google_auth.py`\n"
        )
        chunks = _split_plan_by_phase(plan_text)
        self.assertEqual(len(chunks), 2)
        self.assertTrue(chunks[0].lstrip().startswith("## Phase 1"))
        self.assertNotIn("Key decisions", "".join(chunks))

    def test_h1_named_phase_is_not_dropped(self) -> None:
        # An H1 that IS itself named "Phase" (this repo's existing
        # numbered-marker convention, see test_atx_header_only_plan_unchanged
        # above) must still be kept -- the new drop rule only targets an H1
        # that does NOT mention "Phase" at all.
        plan_text = (
            "# Phase 1\n"
            "- [ ] Task one\n"
            "\n"
            "# Phase 2\n"
            "- [ ] Task two\n"
        )
        chunks = _split_plan_by_phase(plan_text)
        self.assertEqual(len(chunks), 2)

    def test_mark_plan_complete_checks_boxes_when_counts_match(self) -> None:
        plan_text = (
            "<!-- triapi:plan run_id=run1 start -->\n"
            "- [ ] Task one\n"
            "- [ ] Task two\n"
            "<!-- triapi:plan run_id=run1 end -->\n"
        )
        self._write_ags_md(plan_text)
        result = mark_plan_complete(str(self.repo_root), "run1", 2)
        self.assertTrue(result)
        updated_content = self.ags_md_path.read_text()
        self.assertIn("- [x] Task one", updated_content)
        self.assertIn("- [x] Task two", updated_content)

    def test_mark_plan_complete_refuses_when_breakdown_undercounts(self) -> None:
        plan_text = (
            "<!-- triapi:plan run_id=run1 start -->\n"
            "- [ ] Task one\n"
            "- [ ] Task two\n"
            "- [ ] Task three\n"
            "<!-- triapi:plan run_id=run1 end -->\n"
        )
        self._write_ags_md(plan_text)
        result = mark_plan_complete(str(self.repo_root), "run1", 2)
        self.assertFalse(result)
        updated_content = self.ags_md_path.read_text()
        self.assertIn("- [ ] Task one", updated_content)
        self.assertIn("- [ ] Task two", updated_content)
        self.assertIn("- [ ] Task three", updated_content)


if __name__ == "__main__":
    unittest.main()
