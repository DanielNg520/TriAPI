"""Regression tests for the self-fix, lessons, and critique branch features."""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
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

    def _dispatch_crash(self, state: dict, queue):
        with (
            mock.patch.object(triapi.dispatcher, "load_run", return_value=state),
            mock.patch.object(triapi.resource_guard, "pause_services", return_value=[]),
            mock.patch.object(triapi.resource_guard, "resume_services"),
            mock.patch.object(triapi, "load_resource_guard_services", return_value=[]),
            mock.patch.object(triapi, "load_tiers", return_value={"self_fix": {"enabled": True}}),
            mock.patch.object(
                triapi, "_breakdown_and_dispatch", side_effect=RuntimeError("dispatch crash")
            ),
            mock.patch.object(
                triapi.self_fix, "capture_crash", return_value=Path("/tmp/bug.json")
            ),
            mock.patch.object(triapi.self_fix, "queue_self_fix", side_effect=queue) as queued,
        ):
            with self.assertRaisesRegex(RuntimeError, "dispatch crash"):
                triapi.cmd_dispatch(state["run_id"], background=False)
        return queued

    def test_self_fix_marker_skips_auto_queue(self) -> None:
        events: list[str] = []
        state = {
            "run_id": "run-sf",
            "status": "planned",
            "plan_text": "approved",
            "project_dir": str(self_fix.TRIAPI_ROOT.resolve()),
            "self_fix_bug_report": "/tmp/prior.json",
        }
        queued = self._dispatch_crash(state, lambda _p: events.append("queue") or {"status": "queued"})
        queued.assert_not_called()
        self.assertEqual(events, [])

    def test_triapi_rooted_run_without_marker_still_auto_queues(self) -> None:
        events: list[str] = []
        state = {
            "run_id": "run-triapi-feature",
            "status": "planned",
            "plan_text": "approved",
            "project_dir": str(self_fix.TRIAPI_ROOT.resolve()),
        }
        queued = self._dispatch_crash(
            state, lambda _p: events.append("queue") or {"status": "queued", "run_id": "fix"}
        )
        queued.assert_called_once()
        self.assertEqual(events, ["queue"])

    def test_relative_source_files_resolve_against_repo_root_not_cwd(self) -> None:
        report = {
            "exception_type": "RuntimeError",
            "exception_message": "boom",
            "context": "dispatch",
            "traceback": "",
            "source_files": ["scripts/tier1_escalate.py"],
        }
        with mock.patch.object(
            self_fix.planner, "plan_turn", return_value={"status": "ok", "text": "plan"}
        ) as plan_turn:
            with tempfile.TemporaryDirectory() as tmp:
                previous = os.getcwd()
                os.chdir(tmp)
                try:
                    result = self_fix.draft_self_fix_plan(report)
                finally:
                    os.chdir(previous)
        self.assertEqual(result["status"], "ok")
        self.assertIn("scripts/tier1_escalate.py", plan_turn.call_args.args[0])
        self.assertNotIn("(none identified)", plan_turn.call_args.args[0])

    def test_show_ignores_bug_report_outside_bugs_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outside = Path(tmp) / "secret.json"
            outside.write_text('{"secret": true}\n', encoding="utf-8")
            state = {
                "run_id": "r1",
                "status": "self_fix_drafted",
                "self_fix_bug_report": str(outside),
                "plan_text": "draft plan",
            }
            buf = io.StringIO()
            with (
                mock.patch.object(triapi, "_find_self_fix_run", return_value=state),
                mock.patch.object(triapi, "_resolve_bug_report", return_value=None),
                mock.patch("sys.stdout", buf),
            ):
                triapi.cmd_self_fix_show("r1")
            out = buf.getvalue()
            self.assertNotIn("secret", out)
            self.assertIn("No bug report file found", out)
            self.assertIn("draft plan", out)

    def test_approve_flips_drafted_run_to_planned(self) -> None:
        state = {
            "run_id": "r-approve",
            "status": "self_fix_drafted",
            "plan_text": "plan",
        }
        with (
            mock.patch.object(triapi, "_find_self_fix_run", return_value=state),
            mock.patch.object(triapi.dispatcher, "save_run") as save_run,
            mock.patch("sys.stdout", io.StringIO()),
        ):
            triapi.cmd_self_fix_approve("r-approve")
        self.assertEqual(state["status"], "planned")
        save_run.assert_called_once_with(state)

    def test_list_shows_unqueued_bug_stems(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bugs = Path(tmp)
            (bugs / "20260815-bug.json").write_text("{}\n", encoding="utf-8")
            buf = io.StringIO()
            with (
                mock.patch.object(triapi.self_fix, "BUGS_DIR", bugs),
                mock.patch.object(triapi.dispatcher, "list_runs", return_value=[]),
                mock.patch("sys.stdout", buf),
            ):
                triapi.cmd_self_fix_list()
            out = buf.getvalue()
            self.assertIn("20260815-bug", out)
            self.assertIn("(none)", out)


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

    def test_select_relevant_skips_unresolved_pattern(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lessons.jsonl"
            with mock.patch.object(lessons, "LESSONS_PATH", path):
                lessons.add_lesson(
                    "SEARCH/REPLACE regex failed",
                    "empty replacement did not match",
                    "make newline optional",
                    component="scripts/edit_blocks.py",
                    tags=["regex"],
                )
                lessons.add_lesson(
                    "Task x needs human review",
                    "unresolved after tiers",
                    "see log",
                    category="unresolved_pattern",
                    component="scripts/edit_blocks.py",
                    tags=["human_handoff"],
                )
                selected = lessons.select_relevant(
                    "edit_blocks.py", "repair SEARCH replace regex"
                )
        self.assertEqual(len(selected), 1)
        self.assertNotEqual(selected[0]["category"], "unresolved_pattern")

    def test_handoff_writes_runtime_store_not_committed_lessons(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            committed = Path(tmp) / "lessons.jsonl"
            committed.write_text("", encoding="utf-8")
            handoff = Path(tmp) / "handoffs.jsonl"
            with (
                mock.patch.object(lessons, "LESSONS_PATH", committed),
                mock.patch.object(lessons, "HANDOFF_LESSONS_PATH", handoff),
                mock.patch.object(orchestrator, "ESCALATIONS_LOG", Path(tmp) / "esc.jsonl"),
                mock.patch.object(orchestrator, "ESCALATIONS_DIR", Path(tmp)),
            ):
                orchestrator.human_handoff("t1", "reason", component="foo.py")
            self.assertEqual(committed.read_text(encoding="utf-8"), "")
            row = json.loads(handoff.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(row["category"], "unresolved_pattern")
            self.assertEqual(row["component"], "foo.py")


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

    def _low_score_config(self, attempts: int) -> dict:
        return {
            "critique": {
                "enabled": True,
                "applies_to_tiers": ["tier_3"],
                "critic": "tier_1",
                "score_threshold": 7,
                "max_revision_attempts": attempts,
            }
        }

    def test_revision_exception_keeps_passing_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target.py"
            target.write_text("passing\n", encoding="utf-8")

            def explode(*args, **kwargs):
                target.write_text("partial\n", encoding="utf-8")
                raise json.JSONDecodeError("bad", "x", 0)

            with (
                mock.patch.object(
                    orchestrator.critique,
                    "critique_diff",
                    return_value={"status": "ok", "score": 3, "issues": ["quality issue"]},
                ),
                mock.patch.object(orchestrator, "run_build", return_value=(True, "")),
            ):
                orchestrator._critique_and_maybe_revise(
                    "task",
                    str(target),
                    "task description",
                    "tier_3",
                    explode,
                    "check",
                    tmp,
                    "",
                    self._low_score_config(1),
                    "before\n",
                )
            self.assertEqual(target.read_text(encoding="utf-8"), "passing\n")

    def test_zero_revision_attempts_still_scores_but_does_not_revise(self) -> None:
        escalate = mock.Mock()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target.py"
            target.write_text("passing\n", encoding="utf-8")
            with mock.patch.object(
                orchestrator.critique,
                "critique_diff",
                return_value={"status": "ok", "score": 3, "issues": ["quality issue"]},
            ) as critique_diff:
                orchestrator._critique_and_maybe_revise(
                    "task",
                    str(target),
                    "desc",
                    "tier_3",
                    escalate,
                    "check",
                    tmp,
                    "",
                    self._low_score_config(0),
                    "before\n",
                )
        critique_diff.assert_called_once()
        escalate.assert_not_called()

    def test_max_revision_attempts_retries_after_failed_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target.py"
            target.write_text("passing\n", encoding="utf-8")
            calls: list[str] = []

            def escalate(*args, **kwargs):
                calls.append("escalate")
                if len(calls) == 1:
                    return {"status": "fix_rejected", "reason": "no blocks"}
                target.write_text("revised\n", encoding="utf-8")
                return {"status": "fix_applied"}

            with (
                mock.patch.object(
                    orchestrator.critique,
                    "critique_diff",
                    return_value={"status": "ok", "score": 3, "issues": ["quality issue"]},
                ),
                mock.patch.object(orchestrator, "run_build", return_value=(True, "")),
            ):
                orchestrator._critique_and_maybe_revise(
                    "task",
                    str(target),
                    "desc",
                    "tier_3",
                    escalate,
                    "check",
                    tmp,
                    "",
                    self._low_score_config(2),
                    "before\n",
                )
            self.assertEqual(len(calls), 2)
            self.assertEqual(target.read_text(encoding="utf-8"), "revised\n")


class Tier3PeakHoursTests(unittest.TestCase):
    def _check_at(self, utc_dt: datetime) -> dict:
        with (
            mock.patch("scripts.budget_guard.load_tiers", return_value={}),
            mock.patch("scripts.budget_guard.datetime") as fake_dt,
        ):
            fake_dt.now.return_value = utc_dt
            return orchestrator.check_tier3_peak_hours_ok()

    def test_start_of_first_peak_window_refuses(self) -> None:
        result = self._check_at(datetime(2026, 8, 17, 1, 0, tzinfo=timezone.utc))
        self.assertFalse(result["ok"])
        self.assertIn("01:00", result["reason"])
        self.assertIn("LA local", result["reason"])

    def test_mid_off_peak_hour_passes(self) -> None:
        result = self._check_at(datetime(2026, 8, 17, 13, 0, tzinfo=timezone.utc))
        self.assertTrue(result["ok"])

    def test_mid_second_peak_window_refuses(self) -> None:
        result = self._check_at(datetime(2026, 8, 17, 8, 0, tzinfo=timezone.utc))
        self.assertFalse(result["ok"])
        self.assertIn("06:00-10:00", result["reason"])


class OrchestratorTier3PeakSkipTests(unittest.TestCase):
    def _run_task_with_guards(
        self,
        task_id: str,
        description: str,
        target: str,
        tmp: str,
        *,
        tier3_ok: bool,
        tier3_result: dict | None = None,
        tier1_result: dict | None = None,
        tier2_result: dict | None = None,
    ):
        config = {
            "tier_4_worker": {"build_commands": ["true"]},
            "tier_1_manager": {"enabled": True},
            "critique": {"enabled": False},
        }
        tier3_escalate = mock.Mock(
            return_value=tier3_result or {"status": "fix_rejected", "reason": "no"}
        )
        tier1_escalate = mock.Mock(
            return_value=tier1_result or {"status": "fix_rejected", "reason": "no"}
        )
        tier2_escalate = mock.Mock(
            return_value=tier2_result or {"status": "fix_rejected", "reason": "no"}
        )
        with (
            mock.patch.object(orchestrator, "load_tiers", return_value=config),
            mock.patch.object(orchestrator, "build_context_blob", return_value="ctx"),
            mock.patch.object(
                orchestrator,
                "tier4_run",
                side_effect=[
                    {"status": "build_failed", "consecutive_failures": 1},
                    {"status": "escalate"},
                ],
            ),
            mock.patch.object(
                orchestrator,
                "check_tier3_peak_hours_ok",
                return_value={
                    "ok": tier3_ok,
                    "reason": "outside peak hours" if tier3_ok else "inside peak hours",
                },
            ),
            mock.patch.object(orchestrator, "tier3_escalate", new=tier3_escalate),
            mock.patch.object(orchestrator, "check_tier1_ok", return_value={"ok": True}),
            mock.patch.object(
                orchestrator, "check_tier1_manager_ok", return_value={"ok": True}
            ),
            mock.patch.object(orchestrator, "tier1_escalate", new=tier1_escalate),
            mock.patch.object(orchestrator, "check_tier2_ok", return_value={"ok": True}),
            mock.patch.object(orchestrator, "tier2_escalate", new=tier2_escalate),
            mock.patch.object(orchestrator, "read_state", return_value={}),
            mock.patch.object(orchestrator, "report", return_value={}),
            mock.patch.object(orchestrator, "human_handoff"),
        ):
            result = orchestrator.run_task(
                task_id, description, target, workdir=tmp, build_cmd="true"
            )
        return result, tier3_escalate, tier1_escalate, tier2_escalate

    def test_run_task_skips_tier3_escalate_when_peak_hours_not_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = str(Path(tmp) / "target.py")
            result, tier3_escalate, tier1_escalate, _tier2_escalate = (
                self._run_task_with_guards("task-1", "fix it", target, tmp, tier3_ok=False)
            )
        tier3_escalate.assert_not_called()
        tier1_escalate.assert_called_once()
        self.assertEqual(result["status"], "human_handoff")

    def test_run_task_calls_tier3_escalate_when_peak_hours_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = str(Path(tmp) / "target.py")
            result, tier3_escalate, _tier1_escalate, _tier2_escalate = (
                self._run_task_with_guards("task-2", "fix it", target, tmp, tier3_ok=True)
            )
        tier3_escalate.assert_called_once()
        self.assertEqual(result["status"], "human_handoff")

    def test_run_task_falls_through_to_tier2_when_tier3_skipped_and_tier1_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = str(Path(tmp) / "target.py")
            result, tier3_escalate, tier1_escalate, tier2_escalate = (
                self._run_task_with_guards(
                    "task-3",
                    "fix it",
                    target,
                    tmp,
                    tier3_ok=False,
                    tier1_result={"status": "fix_rejected", "reason": "no"},
                )
            )
        tier3_escalate.assert_not_called()
        tier1_escalate.assert_called_once()
        tier2_escalate.assert_called_once_with(
            "task-3",
            target,
            context_blob="ctx",
            description="fix it",
        )
        self.assertEqual(result["status"], "human_handoff")


if __name__ == "__main__":
    unittest.main()
