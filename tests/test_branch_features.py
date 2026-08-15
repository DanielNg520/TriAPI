"""Regression tests for the self-fix, lessons, and critique branch features."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from scripts import cost_report, critique, lessons, orchestrator, self_fix, triapi


class SelfFixTests(unittest.TestCase):
    def test_import_does_not_replace_excepthook(self) -> None:
        self.assertIsNot(sys.excepthook, self_fix.capture_crash)

    def test_capture_crash_writes_structured_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            self_fix, "BUGS_DIR", Path(tmp)
        ):
            try:
                raise RuntimeError("captured failure")
            except RuntimeError as exc:
                report = self_fix.capture_crash(
                    exc, run_id="run-1", context="unit-test"
                )

            self.assertIsNotNone(report)
            data = json.loads(Path(report).read_text(encoding="utf-8"))
            self.assertEqual(data["exception_type"], "RuntimeError")
            self.assertEqual(data["exception_message"], "captured failure")
            self.assertEqual(data["run_id"], "run-1")
            self.assertEqual(data["context"], "unit-test")
            self.assertIn("RuntimeError: captured failure", data["traceback"])

    def test_capture_failure_never_raises(self) -> None:
        with mock.patch.object(self_fix, "BUGS_DIR", Path("/proc/not-writable")):
            report = self_fix.capture_crash(
                RuntimeError("original"), run_id="run-2", context="unit-test"
            )
        self.assertIsNone(report)

    def test_draft_prompt_names_triapi_source_file(self) -> None:
        report = {
            "exception_type": "RuntimeError",
            "exception_message": "boom",
            "context": "dispatch",
            "traceback": 'File "/tmp/elsewhere.py", line 1\n',
            "source_files": ["scripts/tier1_escalate.py"],
        }
        with mock.patch.object(
            self_fix.planner,
            "plan_turn",
            return_value={"status": "ok", "text": "plan"},
        ) as plan_turn:
            result = self_fix.draft_self_fix_plan(report)
        self.assertEqual(result["status"], "ok")
        self.assertIn("scripts/tier1_escalate.py", plan_turn.call_args.args[0])
        self.assertEqual(
            Path(plan_turn.call_args.args[1]).resolve(), self_fix.TRIAPI_ROOT.resolve()
        )

    def test_queue_always_targets_triapi_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bug_dir = Path(tmp)
            report = bug_dir / "bug.json"
            report.write_text(
                json.dumps(
                    {
                        "exception_type": "RuntimeError",
                        "exception_message": "boom",
                        "project_dir": "/attacker/controlled",
                    }
                ),
                encoding="utf-8",
            )
            state = {
                "run_id": "self-fix-run",
                "project_dir": str(self_fix.TRIAPI_ROOT.resolve()),
            }
            with (
                mock.patch.object(self_fix, "BUGS_DIR", bug_dir),
                mock.patch.object(
                    self_fix, "draft_self_fix_plan", return_value={"status": "ok", "text": "plan"}
                ),
                mock.patch.object(self_fix.dispatcher, "new_run", return_value=state) as new_run,
                mock.patch.object(self_fix.dispatcher, "save_run") as save_run,
            ):
                result = self_fix.queue_self_fix(report)

            self.assertEqual(result, {"status": "queued", "run_id": "self-fix-run"})
            self.assertEqual(
                Path(new_run.call_args.kwargs["project_dir"]).resolve(),
                self_fix.TRIAPI_ROOT.resolve(),
            )
            self.assertEqual(state["status"], "self_fix_drafted")
            save_run.assert_called_once_with(state)

    def test_dispatch_resumes_services_before_auto_queue_and_reraises(self) -> None:
        events: list[str] = []
        state = {
            "run_id": "run-3",
            "status": "planned",
            "plan_text": "approved",
            "project_dir": "/tmp/target-project",
        }

        def fail_dispatch(_state):
            raise RuntimeError("dispatch crash")

        def resume(_paused):
            events.append("resume")

        def queue(_path):
            events.append("queue")
            return {"status": "queued", "run_id": "fix-run"}

        with (
            mock.patch.object(triapi.dispatcher, "load_run", return_value=state),
            mock.patch.object(triapi.resource_guard, "pause_services", return_value=["svc"]),
            mock.patch.object(triapi.resource_guard, "resume_services", side_effect=resume),
            mock.patch.object(triapi, "load_resource_guard_services", return_value=[]),
            mock.patch.object(triapi, "load_tiers", return_value={"self_fix": {"enabled": True}}),
            mock.patch.object(triapi, "_breakdown_and_dispatch", side_effect=fail_dispatch),
            mock.patch.object(
                triapi.self_fix, "capture_crash", return_value=Path("/tmp/bug.json")
            ),
            mock.patch.object(triapi.self_fix, "queue_self_fix", side_effect=queue),
        ):
            with self.assertRaisesRegex(RuntimeError, "dispatch crash"):
                triapi.cmd_dispatch("run-3", background=False)

        self.assertEqual(events, ["resume", "queue"])

    def test_bad_config_during_crash_recovery_does_not_mask_original(self) -> None:
        state = {
            "run_id": "run-4",
            "status": "planned",
            "plan_text": "approved",
            "project_dir": "/tmp/target-project",
        }
        with (
            mock.patch.object(triapi.dispatcher, "load_run", return_value=state),
            mock.patch.object(triapi.resource_guard, "pause_services", return_value=[]),
            mock.patch.object(triapi.resource_guard, "resume_services"),
            mock.patch.object(triapi, "load_resource_guard_services", return_value=[]),
            mock.patch.object(triapi, "load_tiers", side_effect=ValueError("bad yaml")),
            mock.patch.object(
                triapi, "_breakdown_and_dispatch", side_effect=RuntimeError("original crash")
            ),
            mock.patch.object(
                triapi.self_fix, "capture_crash", return_value=Path("/tmp/bug.json")
            ),
            mock.patch.object(triapi.self_fix, "queue_self_fix") as queue_self_fix,
        ):
            with self.assertRaisesRegex(RuntimeError, "original crash"):
                triapi.cmd_dispatch("run-4", background=False)
        queue_self_fix.assert_not_called()


class LessonsTests(unittest.TestCase):
    def test_malformed_lines_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lessons.jsonl"
            good = {
                "id": "good",
                "component": "scripts/example.py",
                "tags": [],
                "bug_description": "good lesson",
            }
            path.write_text("not-json\n" + json.dumps(good) + "\n", encoding="utf-8")
            with mock.patch.object(lessons, "LESSONS_PATH", path):
                loaded = lessons.load_lessons()
        self.assertEqual(loaded, [good])

    def test_add_lesson_deduplicates_and_selection_avoids_extension_noise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lessons.jsonl"
            with mock.patch.object(lessons, "LESSONS_PATH", path):
                first = lessons.add_lesson(
                    "SEARCH/REPLACE regex failed",
                    "empty replacement did not match",
                    "make newline optional",
                    component="scripts/edit_blocks.py",
                    tags=["regex"],
                )
                second = lessons.add_lesson(
                    "SEARCH/REPLACE regex failed",
                    "empty replacement did not match",
                    "make newline optional",
                    component="scripts/edit_blocks.py",
                    tags=["regex"],
                )
                selected = lessons.select_relevant(
                    "edit_blocks.py", "repair SEARCH replace regex"
                )
                lines = path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(first, second)
        self.assertEqual(len(lines), 1)
        self.assertEqual(selected[0]["id"], first["id"])


class CritiqueTests(unittest.TestCase):
    def _cli_result(self, result: str) -> SimpleNamespace:
        payload = {
            "result": result,
            "usage": {"input_tokens": 2, "output_tokens": 1},
            "total_cost_usd": 0.01,
            "model": "test-model",
        }
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")

    def test_bad_score_is_advisory_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with (
                mock.patch.object(critique, "COST_LOG_PATH", Path(tmp) / "cost.jsonl"),
                mock.patch(
                    "scripts.budget_guard.check_tier1_ok", return_value={"ok": True}
                ),
                mock.patch.object(
                    critique.subprocess,
                    "run",
                    return_value=self._cli_result(
                        '{"score": "bad", "verdict": "pass", "issues": []}'
                    ),
                ),
            ):
                result = critique.critique_diff("task", "x.py", "fix", "diff")
        self.assertEqual(result["status"], "error")

    def test_threshold_and_string_issue_normalization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with (
                mock.patch.object(critique, "COST_LOG_PATH", Path(tmp) / "cost.jsonl"),
                mock.patch(
                    "scripts.budget_guard.check_tier1_ok", return_value={"ok": True}
                ),
                mock.patch.object(
                    critique.subprocess,
                    "run",
                    return_value=self._cli_result(
                        '{"score": 8, "verdict": "pass", "issues": "simplify"}'
                    ),
                ),
            ):
                result = critique.critique_diff(
                    "task", "x.py", "fix", "diff", score_threshold=9
                )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["verdict"], "revise")
        self.assertEqual(result["issues"], ["simplify"])

    def test_critique_tokens_are_included_in_run_summary(self) -> None:
        summary = cost_report.run_summary(
            [
                {
                    "tier": "critique",
                    "input_tokens": 5,
                    "cache_creation_input_tokens": 2,
                    "cache_read_input_tokens": 3,
                    "output_tokens": 4,
                    "cost_usd": 0.0,
                    "notional_cost_usd": 0.1,
                }
            ]
        )
        self.assertEqual(summary["critique"]["input_tokens"], 10)
        self.assertEqual(summary["critique"]["output_tokens"], 4)

    def test_failed_revision_reverts_passing_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target.py"
            target.write_text("passing\n", encoding="utf-8")

            def revise(*args, **kwargs):
                self.assertIn("quality issue", kwargs["revision_note"])
                self.assertEqual(kwargs["description"], "task description")
                target.write_text("broken revision\n", encoding="utf-8")
                return {"status": "fix_applied"}

            config = {
                "critique": {
                    "enabled": True,
                    "applies_to_tiers": ["tier_3"],
                    "critic": "tier_1",
                    "score_threshold": 7,
                    "max_revision_attempts": 1,
                }
            }
            with (
                mock.patch.object(
                    orchestrator.critique,
                    "critique_diff",
                    return_value={
                        "status": "ok",
                        "score": 3,
                        "issues": ["quality issue"],
                    },
                ),
                mock.patch.object(orchestrator, "run_build", return_value=(False, "bad")),
            ):
                orchestrator._critique_and_maybe_revise(
                    "task",
                    str(target),
                    "task description",
                    "tier_3",
                    revise,
                    "check",
                    tmp,
                    "",
                    config,
                    "before\n",
                )
            self.assertEqual(target.read_text(encoding="utf-8"), "passing\n")

    def test_invalid_numeric_config_skips_critique(self) -> None:
        with mock.patch.object(orchestrator.critique, "critique_diff") as critique_diff:
            orchestrator._critique_and_maybe_revise(
                "task",
                "/does/not/matter.py",
                "description",
                "tier_3",
                mock.Mock(),
                "check",
                ".",
                "",
                {
                    "critique": {
                        "enabled": True,
                        "applies_to_tiers": ["tier_3"],
                        "critic": "tier_1",
                        "score_threshold": "invalid",
                        "max_revision_attempts": 1,
                    }
                },
                "before",
            )
        critique_diff.assert_not_called()


if __name__ == "__main__":
    unittest.main()
