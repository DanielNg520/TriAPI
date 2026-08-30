"""Regression test for scripts.triapi._breakdown_and_dispatch's final summary
print loop.

Real incident 2026-08-29: a run's `results` list contained an entry that a
supervisor had hand-corrected in the stored run JSON (matching this repo's
own "verify, don't trust status" convention -- e.g. reversing a false
success/failure the pipeline itself got wrong) but the hand-edit omitted the
'item'/'phase' keys every pipeline-produced entry normally carries. The
summary print loop's `r['phase']`/`r['item']` (dict-subscript, not `.get()`)
raised KeyError, crashing _breakdown_and_dispatch before it ever reached
`agents_md_gate.mark_plan_complete()` -- so a run whose state was already
"completed" (all real work done and verified) silently never got its
AGENTS.md checkboxes ticked, requiring a second manual intervention to
resume. Fixed by using `.get()` with sane fallbacks in the print line.
"""

from __future__ import annotations

import unittest
from unittest import mock

from scripts import triapi


class BreakdownAndDispatchSummaryPrintTests(unittest.TestCase):
    def test_missing_item_and_phase_keys_do_not_crash_the_summary_loop(self) -> None:
        state = {
            "run_id": "run-missing-keys",
            "project_dir": "/tmp/project-dir",
            "breakdown": {"phases": [{"name": "p", "items": [{"target": "f.py"}]}]},
        }
        dispatched_state = {
            **state,
            "status": "completed",
            "results": [
                {
                    "task_id": "run-missing-keys-p0-i0",
                    "status": "success",
                    "resolved_by": "verify",
                    # 'phase' and 'item' deliberately omitted, mirroring a
                    # hand-corrected entry that skipped the normal schema.
                }
            ],
        }

        with (
            mock.patch.object(triapi.dispatcher, "breakdown_plan", return_value={"status": "ok"}),
            mock.patch.object(triapi.dispatcher, "dispatch", return_value=dispatched_state),
            mock.patch.object(triapi, "cost_report", return_value={"total_actual_usd": 0.0}),
            mock.patch.object(triapi, "load_entries", return_value=[]),
            mock.patch.object(triapi, "format_run_report", return_value=""),
            mock.patch.object(triapi.agents_md_gate, "mark_plan_complete") as mark_plan_complete,
            mock.patch.object(triapi.budget_guard, "check_jules_ok", return_value={"ok": False, "reason": "disabled"}),
        ):
            # Must not raise -- this is the exact crash from the incident.
            triapi._breakdown_and_dispatch(state)

        mark_plan_complete.assert_called_once_with(
            state["project_dir"], state["run_id"], 1
        )


if __name__ == "__main__":
    unittest.main()
