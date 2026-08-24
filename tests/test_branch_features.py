"""Regression tests for the self-fix, lessons, and critique branch features."""

from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from scripts import (
    agents_md_gate,
    budget_guard,
    cost_report,
    critique,
    dispatcher,
    edit_blocks,
    git_ops,
    jules_client,
    lessons,
    llm_client,
    orchestrator,
    resource_guard,
    self_fix,
    tech_debt,
    tier3_escalate,
    triapi,
)


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
            mock.patch.object(triapi.llm_client, "probe_models"),
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
            mock.patch.object(triapi.llm_client, "probe_models"),
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
            mock.patch.object(triapi.llm_client, "probe_models"),
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

    def test_early_morning_off_peak_passes(self) -> None:
        # 00:30 UTC is before the first peak window (01:00-04:00 UTC) starts.
        result = self._check_at(datetime(2026, 8, 17, 0, 30, tzinfo=timezone.utc))
        self.assertTrue(result["ok"])

    def test_mid_off_peak_hour_passes(self) -> None:
        result = self._check_at(datetime(2026, 8, 17, 13, 0, tzinfo=timezone.utc))
        self.assertTrue(result["ok"])

    def test_mid_second_peak_window_refuses(self) -> None:
        result = self._check_at(datetime(2026, 8, 17, 8, 0, tzinfo=timezone.utc))
        self.assertFalse(result["ok"])
        self.assertIn("06:00-10:00", result["reason"])

    def test_weekend_passes_in_peak(self) -> None:
        # Aug 23, 2026 is a Sunday in Beijing Time.
        result = self._check_at(datetime(2026, 8, 23, 8, 0, tzinfo=timezone.utc))
        self.assertTrue(result["ok"])
        self.assertIn("weekend off-peak", result["reason"].lower())

    def test_weekday_refuses_in_peak(self) -> None:
        # Aug 24, 2026 is a Monday. Regular peak hours apply.
        result = self._check_at(datetime(2026, 8, 24, 8, 0, tzinfo=timezone.utc))
        self.assertFalse(result["ok"])
        self.assertIn("06:00-10:00", result["reason"])


class LlmClientOpenAIErrorBodyTests(unittest.TestCase):
    def _fake_response(self, status_code, json_body):
        fake = mock.Mock()
        fake.status_code = status_code
        fake.raise_for_status = mock.Mock()
        fake.json = mock.Mock(return_value=json_body)
        fake.content = json.dumps(json_body).encode()
        return fake

    def test_embedded_error_with_code_sets_response_status(self):
        data = {"error": {"code": 429, "message": "rate limited"}}
        fake = self._fake_response(200, data)
        with mock.patch.object(llm_client.requests, "post", return_value=fake):
            with self.assertRaises(Exception) as ctx:
                llm_client._call_openai_api(
                    "https://openrouter.ai/api/v1",
                    "key",
                    "nvidia/nemotron-3-ultra-550b-a55b:free",
                    "prompt",
                    "system",
                    "openrouter",
                )
        self.assertEqual(
            getattr(getattr(ctx.exception, "response", None), "status_code", None), 429
        )

    def test_missing_choices_no_error_key_raises_clear_message(self):
        data = {"weird": "shape"}
        fake = self._fake_response(200, data)
        with mock.patch.object(llm_client.requests, "post", return_value=fake):
            with self.assertRaises(Exception) as ctx:
                llm_client._call_openai_api(
                    "https://openrouter.ai/api/v1",
                    "key",
                    "nvidia/nemotron-3-ultra-550b-a55b:free",
                    "prompt",
                    "system",
                    "openrouter",
                )
        self.assertIn("unexpected response shape", str(ctx.exception))
        self.assertNotEqual(str(ctx.exception), "'choices'")

    def test_normal_response_with_choices_still_works(self):
        data = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 2},
        }
        fake = self._fake_response(200, data)
        with mock.patch.object(llm_client.requests, "post", return_value=fake):
            result = llm_client._call_openai_api(
                "https://openrouter.ai/api/v1",
                "key",
                "nvidia/nemotron-3-ultra-550b-a55b:free",
                "prompt",
                "system",
                "openrouter",
            )
        self.assertEqual(result, ("ok", "openrouter", 1, 2))


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
            result, tier3_escalate, _tier1_escalate, tier2_escalate = (
                self._run_task_with_guards("task-1", "fix it", target, tmp, tier3_ok=False)
            )
        tier3_escalate.assert_not_called()
        tier2_escalate.assert_called_once()
        self.assertEqual(result["status"], "human_handoff")

    def test_run_task_calls_tier3_escalate_when_peak_hours_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = str(Path(tmp) / "target.py")
            result, tier3_escalate, _tier1_escalate, _tier2_escalate = (
                self._run_task_with_guards("task-2", "fix it", target, tmp, tier3_ok=True)
            )
        tier3_escalate.assert_called_once()
        self.assertEqual(result["status"], "human_handoff")

    def test_run_task_falls_through_to_tier1_when_tier3_skipped_and_tier2_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = str(Path(tmp) / "target.py")
            result, tier3_escalate, tier1_escalate, tier2_escalate = (
                self._run_task_with_guards(
                    "task-3",
                    "fix it",
                    target,
                    tmp,
                    tier3_ok=False,
                    tier2_result={"status": "fix_rejected", "reason": "no"},
                )
            )
        tier3_escalate.assert_not_called()
        tier2_escalate.assert_called_once()
        tier1_escalate.assert_called_once_with(
            "task-3",
            target,
            context_blob="ctx",
            description="fix it",
        )
        self.assertEqual(result["status"], "human_handoff")


class SkipTier4Tests(unittest.TestCase):
    """run_task(skip_tier4=True) -- the file-size-ceiling escape hatch
    (dispatcher._enforce_file_size_ceiling marks items on an oversized
    target this way) must never invoke Tier 4 at all and go straight to
    Tier 3."""

    def test_skip_tier4_never_calls_tier4_run_and_starts_at_tier3(self) -> None:
        config = {
            "tier_4_worker": {"build_commands": ["true"]},
            "tier_1_manager": {"enabled": True},
            "critique": {"enabled": False},
        }
        tier4_run = mock.Mock()
        tier3_escalate = mock.Mock(return_value={"status": "fix_rejected", "reason": "no"})
        with tempfile.TemporaryDirectory() as tmp:
            target = str(Path(tmp) / "target.py")
            with (
                mock.patch.object(orchestrator, "load_tiers", return_value=config),
                mock.patch.object(orchestrator, "build_context_blob", return_value="ctx"),
                mock.patch.object(orchestrator, "tier4_run", new=tier4_run),
                mock.patch.object(
                    orchestrator, "check_tier3_peak_hours_ok", return_value={"ok": True}
                ),
                mock.patch.object(orchestrator, "tier3_escalate", new=tier3_escalate),
                mock.patch.object(orchestrator, "check_tier2_ok", return_value={"ok": False, "reason": "no"}),
                mock.patch.object(orchestrator, "check_tier1_ok", return_value={"ok": False, "reason": "no"}),
                mock.patch.object(
                    orchestrator, "check_tier1_manager_ok", return_value={"ok": True}
                ),
                mock.patch.object(orchestrator, "read_state", return_value={}),
                mock.patch.object(orchestrator, "report", return_value={}),
                mock.patch.object(orchestrator, "human_handoff"),
            ):
                result = orchestrator.run_task(
                    "task-skip4", "fix it", target, workdir=tmp, build_cmd="true",
                    skip_tier4=True,
                )
        tier4_run.assert_not_called()
        tier3_escalate.assert_called_once()
        self.assertEqual(result["status"], "human_handoff")

    def test_skip_tier4_defaults_false_and_calls_tier4_run(self) -> None:
        config = {
            "tier_4_worker": {"build_commands": ["true"]},
            "tier_1_manager": {"enabled": True},
            "critique": {"enabled": False},
        }
        tier4_run = mock.Mock(return_value={"status": "success", "consecutive_failures": 0})
        with tempfile.TemporaryDirectory() as tmp:
            target = str(Path(tmp) / "target.py")
            with (
                mock.patch.object(orchestrator, "load_tiers", return_value=config),
                mock.patch.object(orchestrator, "build_context_blob", return_value="ctx"),
                mock.patch.object(orchestrator, "tier4_run", new=tier4_run),
                mock.patch.object(orchestrator, "read_state", return_value={}),
                mock.patch.object(orchestrator, "report", return_value={}),
            ):
                result = orchestrator.run_task(
                    "task-noskip4", "fix it", target, workdir=tmp, build_cmd="true",
                )
        tier4_run.assert_called_once()
        self.assertEqual(result["status"], "success")


class JulesClientUnavailableTests(unittest.TestCase):
    def test_missing_api_key_short_circuits(self) -> None:
        with (
            mock.patch.object(jules_client, "load_secrets", return_value={}),
            mock.patch.object(jules_client, "create_session") as create_session,
            mock.patch.object(jules_client.requests, "post") as post,
        ):
            result = jules_client.run_jules_test(prompt="p", source="s")
        self.assertEqual(result["status"], "error")
        self.assertIn("google_jules_apikey", result["reason"])
        create_session.assert_not_called()
        post.assert_not_called()


class JulesClientErrorTests(unittest.TestCase):
    def test_create_session_request_exception_returns_error(self) -> None:
        with (
            mock.patch.object(
                jules_client, "load_secrets", return_value={"google_jules_apikey": "k"}
            ),
            mock.patch.object(
                jules_client,
                "create_session",
                side_effect=jules_client.requests.RequestException("boom"),
            ),
        ):
            result = jules_client.run_jules_test(prompt="p", source="s")
        self.assertEqual(result["status"], "error")
        self.assertIn("create_session failed", result["reason"])


class JulesPollResultOkTests(unittest.TestCase):
    def test_completed_state_returns_ok_summary(self) -> None:
        with (
            mock.patch.object(
                jules_client, "get_session_state", return_value={"state": "COMPLETED"}
            ),
            mock.patch.object(
                jules_client, "get_final_message", return_value="mock summary"
            ),
            mock.patch.object(jules_client.time, "sleep") as sleep_mock,
        ):
            result = jules_client.poll_session_result("sessions/abc", "key")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["final_message"], "mock summary")
        sleep_mock.assert_not_called()


class JulesGetFinalMessageTests(unittest.TestCase):
    def test_parses_real_confirmed_live_activity_shape(self) -> None:
        # Real shape confirmed live 2026-08-17 against the actual Jules API
        # (see AGENTS.md / logs/jules_tester_integration_plan_prompt.txt):
        # the reply text lives at activity["agentMessaged"]["agentMessage"],
        # not ["message"] -- this test pins that field name against
        # regression.
        activities_response = {
            "activities": [
                {"originator": "agent", "planGenerated": {"plan": {"id": "p1", "steps": []}}},
                {"originator": "user", "planApproved": {"planId": "p1"}},
                {"originator": "agent", "progressUpdated": {"title": "Running tests"}},
                {"originator": "agent", "agentMessaged": {"agentMessage": "CONFIRMED"}},
            ]
        }
        resp = mock.Mock()
        resp.json.return_value = activities_response
        resp.raise_for_status = mock.Mock()
        with mock.patch.object(jules_client.requests, "get", return_value=resp):
            result = jules_client.get_final_message("sessions/abc", "key")
        self.assertEqual(result, "CONFIRMED")


class JulesPollResultFailedTests(unittest.TestCase):
    def test_failed_state_returns_failed_status(self) -> None:
        with (
            mock.patch.object(
                jules_client, "get_session_state", return_value={"state": "FAILED"}
            ),
            mock.patch.object(jules_client, "get_final_message", return_value=None),
            mock.patch.object(jules_client.time, "sleep"),
        ):
            result = jules_client.poll_session_result("sessions/abc", "key")
        self.assertEqual(result["status"], "failed")


class JulesPollResultTimeoutTests(unittest.TestCase):
    def test_nonterminal_state_past_deadline_returns_timeout(self) -> None:
        with (
            mock.patch.object(
                jules_client.time, "monotonic", side_effect=[0, 1]
            ),
            mock.patch.object(
                jules_client, "get_session_state", return_value={"state": "RUNNING"}
            ),
            mock.patch.object(jules_client.time, "sleep") as sleep_mock,
        ):
            result = jules_client.poll_session_result(
                "sessions/abc", "key", timeout=0
            )
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["state"], "RUNNING")
        sleep_mock.assert_not_called()


class CheckJulesOkTests(unittest.TestCase):
    def test_under_limit_reports_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "jules_usage.jsonl"
            log_path.write_text(
                json.dumps({"timestamp": time.time()}) + "\n", encoding="utf-8"
            )
            with (
                mock.patch.object(budget_guard, "JULES_USAGE_LOG", log_path),
                mock.patch.object(
                    budget_guard,
                    "load_tiers",
                    return_value={"jules_tester": {"daily_task_limit": 5}},
                ),
            ):
                result = budget_guard.check_jules_ok()
        self.assertTrue(result["ok"])
        self.assertIn("1/5", result["reason"])

    def test_at_limit_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "jules_usage.jsonl"
            lines = "\n".join(
                json.dumps({"timestamp": time.time()}) for _ in range(3)
            )
            log_path.write_text(lines + "\n", encoding="utf-8")
            with (
                mock.patch.object(budget_guard, "JULES_USAGE_LOG", log_path),
                mock.patch.object(
                    budget_guard,
                    "load_tiers",
                    return_value={"jules_tester": {"daily_task_limit": 3}},
                ),
            ):
                result = budget_guard.check_jules_ok()
        self.assertFalse(result["ok"])
        self.assertIn("3/3", result["reason"])


class BreakdownDispatchJulesHookTests(unittest.TestCase):
    def _completed_state(self) -> dict:
        return {
            "run_id": "run-jules",
            "project_dir": "/tmp/proj",
            "prompt": "do stuff",
            "breakdown": {"phases": []},
            "results": [],
            "status": "completed",
        }

    def test_jules_test_skipped_when_budget_check_refuses(self) -> None:
        state = self._completed_state()
        with (
            mock.patch.object(
                triapi.dispatcher, "breakdown_plan", return_value={"status": "ok"}
            ),
            mock.patch.object(triapi.dispatcher, "dispatch", return_value=state),
            mock.patch.object(triapi.dispatcher, "save_run"),
            mock.patch.object(triapi, "load_entries", return_value=[]),
            mock.patch.object(triapi, "format_run_report", return_value=""),
            mock.patch.object(
                triapi.budget_guard,
                "check_jules_ok",
                return_value={"ok": False, "reason": "limit reached"},
            ),
            mock.patch.object(triapi.git_ops, "push") as push_mock,
            mock.patch.object(triapi.jules_client, "run_jules_test") as run_jules_test,
            mock.patch("sys.stdout", io.StringIO()),
        ):
            triapi._breakdown_and_dispatch(state)
        push_mock.assert_not_called()
        run_jules_test.assert_not_called()

    def test_jules_test_dispatched_when_budget_ok_and_push_succeeds(self) -> None:
        state = self._completed_state()
        with (
            mock.patch.object(
                triapi.dispatcher, "breakdown_plan", return_value={"status": "ok"}
            ),
            mock.patch.object(triapi.dispatcher, "dispatch", return_value=state),
            mock.patch.object(triapi.dispatcher, "save_run"),
            mock.patch.object(triapi, "load_entries", return_value=[]),
            mock.patch.object(triapi, "format_run_report", return_value=""),
            mock.patch.object(
                triapi.budget_guard,
                "check_jules_ok",
                return_value={"ok": True, "reason": "within limit"},
            ),
            mock.patch.object(
                triapi.budget_guard, "record_jules_call"
            ) as record_call,
            mock.patch.object(
                triapi.git_ops,
                "get_github_owner_repo",
                return_value=("owner", "repo"),
            ),
            mock.patch.object(
                triapi.git_ops,
                "push",
                return_value={"ok": True, "branch": "triapi/foo"},
            ) as push_mock,
            mock.patch.object(
                triapi,
                "load_tiers",
                return_value={"jules_tester": {"source": "sources/github/owner/repo"}},
            ),
            mock.patch.object(
                triapi.jules_client,
                "run_jules_test",
                return_value={"status": "completed", "final_message": "done"},
            ) as run_jules_test,
            mock.patch("sys.stdout", io.StringIO()),
        ):
            triapi._breakdown_and_dispatch(state)
        push_mock.assert_called_once()
        run_jules_test.assert_called_once()
        record_call.assert_called_once()

    def test_jules_test_skipped_when_push_fails(self) -> None:
        state = self._completed_state()
        with (
            mock.patch.object(
                triapi.dispatcher, "breakdown_plan", return_value={"status": "ok"}
            ),
            mock.patch.object(triapi.dispatcher, "dispatch", return_value=state),
            mock.patch.object(triapi.dispatcher, "save_run"),
            mock.patch.object(triapi, "load_entries", return_value=[]),
            mock.patch.object(triapi, "format_run_report", return_value=""),
            mock.patch.object(
                triapi.budget_guard,
                "check_jules_ok",
                return_value={"ok": True, "reason": "within limit"},
            ),
            mock.patch.object(
                triapi.git_ops,
                "push",
                return_value={"ok": False, "output": "push failed"},
            ) as push_mock,
            mock.patch.object(triapi.jules_client, "run_jules_test") as run_jules_test,
            mock.patch("sys.stdout", io.StringIO()),
        ):
            triapi._breakdown_and_dispatch(state)
        push_mock.assert_called_once()
        run_jules_test.assert_not_called()


class AgentsMdGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.project_dir = self.tmpdir.name

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_no_agents_md_means_no_incomplete_plan(self) -> None:
        self.assertIsNone(agents_md_gate.find_incomplete_plan(self.project_dir))

    def test_append_then_find_incomplete(self) -> None:
        plan = "## Phase 1\n- [ ] step one\n- [ ] step two\n"
        agents_md_gate.append_plan(self.project_dir, "run-1", plan, "2026-08-16")
        incomplete = agents_md_gate.find_incomplete_plan(self.project_dir)
        self.assertIsNotNone(incomplete)
        self.assertEqual(incomplete["run_id"], "run-1")
        self.assertEqual(incomplete["unchecked_count"], 2)

    def test_append_creates_file_with_header(self) -> None:
        agents_md_gate.append_plan(self.project_dir, "run-1", "- [ ] a step", "2026-08-16")
        text = Path(self.project_dir, "AGENTS.md").read_text()
        self.assertIn("# AGENTS.md", text)
        self.assertIn("run_id=run-1", text)

    def test_mark_plan_complete_clears_gate(self) -> None:
        plan = "- [ ] step one\n- [ ] step two\n"
        agents_md_gate.append_plan(self.project_dir, "run-1", plan, "2026-08-16")
        ok = agents_md_gate.mark_plan_complete(
            self.project_dir, "run-1", breakdown_item_count=2
        )
        self.assertTrue(ok)
        self.assertIsNone(agents_md_gate.find_incomplete_plan(self.project_dir))
        text = Path(self.project_dir, "AGENTS.md").read_text()
        self.assertNotIn("[ ]", text)
        self.assertIn("[x]", text)

    def test_mark_plan_complete_unknown_run_is_noop(self) -> None:
        agents_md_gate.append_plan(self.project_dir, "run-1", "- [ ] step", "2026-08-16")
        ok = agents_md_gate.mark_plan_complete(
            self.project_dir, "run-nope", breakdown_item_count=1
        )
        self.assertFalse(ok)
        self.assertIsNotNone(agents_md_gate.find_incomplete_plan(self.project_dir))

    def test_only_most_recent_block_gates(self) -> None:
        agents_md_gate.append_plan(self.project_dir, "run-1", "- [ ] step", "2026-08-16")
        agents_md_gate.mark_plan_complete(
            self.project_dir, "run-1", breakdown_item_count=1
        )
        agents_md_gate.append_plan(self.project_dir, "run-2", "- [ ] another step", "2026-08-17")
        incomplete = agents_md_gate.find_incomplete_plan(self.project_dir)
        self.assertEqual(incomplete["run_id"], "run-2")

    def test_block_with_no_checkboxes_is_not_blocking(self) -> None:
        agents_md_gate.append_plan(self.project_dir, "run-1", "Just prose, no checklist.", "2026-08-16")
        self.assertIsNone(agents_md_gate.find_incomplete_plan(self.project_dir))


class CmdPlanRefactorGateTests(unittest.TestCase):
    def test_refuses_when_incomplete_plan_exists(self) -> None:
        with (
            mock.patch.object(
                triapi.agents_md_gate,
                "find_incomplete_plan",
                return_value={"run_id": "run-1", "unchecked_count": 3},
            ),
            mock.patch.object(triapi.dispatcher, "new_run") as new_run_mock,
            mock.patch("sys.stdout", io.StringIO()) as out,
        ):
            triapi.cmd_plan("do something", "/some/project")
        new_run_mock.assert_not_called()
        self.assertIn("run-1", out.getvalue())
        self.assertIn("--refactor", out.getvalue())

    def test_refactor_flag_bypasses_gate(self) -> None:
        with (
            mock.patch.object(triapi.agents_md_gate, "find_incomplete_plan") as find_mock,
            mock.patch.object(
                triapi.dispatcher,
                "new_run",
                return_value={"run_id": "run-2", "prompt": "p", "project_dir": "/x"},
            ),
            mock.patch.object(
                triapi.planner, "plan_turn",
                return_value={"status": "ok", "text": "plan", "session_id": "s", "notional_cost_usd": 0.0},
            ),
            mock.patch("builtins.input", return_value="cancel"),
            mock.patch.object(triapi.dispatcher, "save_run"),
            mock.patch("sys.stdout", io.StringIO()),
        ):
            triapi.cmd_plan("do something", "/some/project", refactor=True)
        find_mock.assert_not_called()


class UnloadOllamaModelsTests(unittest.TestCase):
    def test_unload_models_successful(self) -> None:
        mock_get_resp = mock.Mock()
        mock_get_resp.raise_for_status = mock.Mock()
        mock_get_resp.json.return_value = {
            "models": [
                {"name": "keep"},
                {"name": "other1"},
                {"name": "other2"},
            ]
        }

        def post_side_effect(url, json):
            resp = mock.Mock()
            resp.raise_for_status = mock.Mock()
            return resp

        with (
            mock.patch.object(resource_guard.requests, "get", return_value=mock_get_resp),
            mock.patch.object(
                resource_guard.requests, "post", side_effect=post_side_effect
            ) as mock_post
        ):
            unloaded = resource_guard.unload_other_ollama_models(
                "keep", "http://localhost:11434"
            )
            self.assertEqual(set(unloaded), {"other1", "other2"})
            mock_post.assert_has_calls(
                [
                    mock.call(
                        "http://localhost:11434/api/generate",
                        json={"model": "other1", "keep_alive": 0},
                    ),
                    mock.call(
                        "http://localhost:11434/api/generate",
                        json={"model": "other2", "keep_alive": 0},
                    ),
                ],
                any_order=True,
            )

    def test_unload_models_get_exception_returns_empty(self) -> None:
        with mock.patch.object(
            resource_guard.requests,
            "get",
            side_effect=resource_guard.requests.RequestException("boom"),
        ):
            unloaded = resource_guard.unload_other_ollama_models(
                "keep", "http://localhost:11434"
            )
            self.assertEqual(unloaded, [])

    def test_unload_models_partial_failure(self) -> None:
        mock_get_resp = mock.Mock()
        mock_get_resp.raise_for_status = mock.Mock()
        mock_get_resp.json.return_value = {
            "models": [
                {"name": "other1"},
                {"name": "other2"},
            ]
        }

        def post_side_effect(url, json):
            if json["model"] == "other1":
                raise resource_guard.requests.RequestException("fail")
            resp = mock.Mock()
            resp.raise_for_status = mock.Mock()
            return resp

        with (
            mock.patch.object(resource_guard.requests, "get", return_value=mock_get_resp),
            mock.patch.object(
                resource_guard.requests, "post", side_effect=post_side_effect
            ) as mock_post
        ):
            unloaded = resource_guard.unload_other_ollama_models(
                "", "http://localhost:11434"
            )
            self.assertEqual(unloaded, ["other2"])
            mock_post.assert_has_calls(
                [
                    mock.call(
                        "http://localhost:11434/api/generate",
                        json={"model": "other1", "keep_alive": 0},
                    ),
                    mock.call(
                        "http://localhost:11434/api/generate",
                        json={"model": "other2", "keep_alive": 0},
                    ),
                ],
                any_order=True,
            )


class DispatcherHookAndFixForwardTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.project_dir = self.tmpdir.name
        self.target_file = Path(self.project_dir) / "test_file.py"
        self.target_file.write_text("original content\n", encoding="utf-8")

    def tearDown(self):
        self.tmpdir.cleanup()

    @mock.patch("scripts.dispatcher.save_run")
    @mock.patch("scripts.dispatcher.check_tier2_ok", return_value={"ok": True})
    @mock.patch("scripts.dispatcher.run_task")
    @mock.patch("scripts.judge.evaluate_design")
    @mock.patch("scripts.judge.extract_pattern")
    @mock.patch("scripts.dispatcher.handle_fix_forward")
    @mock.patch("subprocess.run")
    def test_successful_item_passing_judge_calls_extract_pattern(
        self, mock_run, mock_handle_ff, mock_extract, mock_eval, mock_run_task, mock_check_ok, mock_save
    ):
        mock_run_task.return_value = {"status": "success", "resolved_by": "tier_3"}
        mock_eval.return_value = {"status": "ok", "approved": True, "reason": "looks good", "cost_usd": 0.01}
        mock_run.return_value = SimpleNamespace(returncode=0, stdout="diff content", stderr="")

        state = {
            "run_id": "run-test",
            "project_dir": self.project_dir,
            "status": "planned",
            "breakdown": {
                "phases": [
                    {
                        "name": "Phase 1",
                        "items": [
                            {
                                "description": "Test task",
                                "target": str(self.target_file.relative_to(self.project_dir)),
                                "build_cmd": "echo 'built'",
                                "verify_only": False,
                                "context_files": []
                            }
                        ]
                    }
                ]
            },
            "results": []
        }

        dispatcher.dispatch(state)

        mock_eval.assert_called_once()
        mock_extract.assert_called_once()
        mock_handle_ff.assert_not_called()

    @mock.patch("scripts.dispatcher.save_run")
    @mock.patch("scripts.dispatcher.check_tier2_ok", return_value={"ok": True})
    @mock.patch("scripts.dispatcher.run_task")
    @mock.patch("scripts.judge.evaluate_design")
    @mock.patch("scripts.judge.extract_pattern")
    @mock.patch("scripts.dispatcher.handle_fix_forward")
    @mock.patch("subprocess.run")
    def test_successful_item_failing_judge_calls_handle_fix_forward(
        self, mock_run, mock_handle_ff, mock_extract, mock_eval, mock_run_task, mock_check_ok, mock_save
    ):
        mock_run_task.return_value = {"status": "success", "resolved_by": "tier_3"}
        mock_eval.return_value = {"status": "ok", "approved": False, "reason": "bad design", "cost_usd": 0.01}
        mock_run.return_value = SimpleNamespace(returncode=0, stdout="diff content", stderr="")

        state = {
            "run_id": "run-test",
            "project_dir": self.project_dir,
            "status": "planned",
            "breakdown": {
                "phases": [
                    {
                        "name": "Phase 1",
                        "items": [
                            {
                                "description": "Test task",
                                "target": str(self.target_file.relative_to(self.project_dir)),
                                "build_cmd": "echo 'built'",
                                "verify_only": False,
                                "context_files": []
                            }
                        ]
                    }
                ]
            },
            "results": []
        }

        dispatcher.dispatch(state)

        mock_eval.assert_called_once()
        mock_extract.assert_not_called()
        mock_handle_ff.assert_called_once()

    @mock.patch("scripts.dispatcher.save_run")
    @mock.patch("scripts.dispatcher.check_tier2_ok", return_value={"ok": True})
    @mock.patch("scripts.dispatcher.run_task")
    @mock.patch("scripts.judge.evaluate_design")
    @mock.patch("scripts.judge.extract_pattern")
    @mock.patch("scripts.dispatcher.handle_fix_forward")
    @mock.patch("subprocess.run")
    def test_peak_hours_skipped_judge_passes_open_calls_extract_pattern(
        self, mock_run, mock_handle_ff, mock_extract, mock_eval, mock_run_task, mock_check_ok, mock_save
    ):
        mock_run_task.return_value = {"status": "success", "resolved_by": "tier_3"}
        mock_eval.return_value = {"status": "skipped", "approved": True, "reason": "peak_hours", "cost_usd": 0.0}
        mock_run.return_value = SimpleNamespace(returncode=0, stdout="diff content", stderr="")

        state = {
            "run_id": "run-test",
            "project_dir": self.project_dir,
            "status": "planned",
            "breakdown": {
                "phases": [
                    {
                        "name": "Phase 1",
                        "items": [
                            {
                                "description": "Test task",
                                "target": str(self.target_file.relative_to(self.project_dir)),
                                "build_cmd": "echo 'built'",
                                "verify_only": False,
                                "context_files": []
                            }
                        ]
                    }
                ]
            },
            "results": []
        }

        dispatcher.dispatch(state)

        mock_eval.assert_called_once()
        mock_extract.assert_called_once()
        mock_handle_ff.assert_not_called()

    @mock.patch("subprocess.run")
    @mock.patch("scripts.tier3_escalate.escalate", autospec=True)
    @mock.patch("scripts.dispatcher.run_build")
    @mock.patch("scripts.tech_debt.log_tech_debt")
    def test_handle_fix_forward_successful_rebuild(self, mock_log_tech_debt, mock_run_build, mock_escalate, mock_run):
        self.target_file.write_text("original content\n", encoding="utf-8")
        
        def mock_escalate_side_effect(*args, **kwargs):
            self.target_file.write_text("tier 3 rewrite\n", encoding="utf-8")
            return {"status": "fix_applied"}
            
        mock_escalate.side_effect = mock_escalate_side_effect
        mock_run_build.return_value = (True, "build ok")
        mock_run.return_value = SimpleNamespace(returncode=0, stdout="diff content", stderr="")

        import inspect
        sig = inspect.signature(dispatcher.handle_fix_forward)
        kwargs = {}
        param_mapping = {
            "task_id": "task-test",
            "target": str(self.target_file),
            "snapshot": "original content\n",
            "build_cmd": "echo 'built'",
            "workdir": self.project_dir,
            "description": "Test description",
            "context_blob": "",
            "revision_note": "",
            "refactor_instruction": "",
            "state": {
                "run_id": "run-test",
                "project_dir": self.project_dir,
                "status": "planned",
                "breakdown": {"phases": []},
                "results": [],
            },
            "item": {
                "description": "Test description",
                "target": str(self.target_file.relative_to(self.project_dir)),
                "build_cmd": "echo 'built'",
            }
        }
        for name in sig.parameters:
            if name in param_mapping:
                kwargs[name] = param_mapping[name]

        dispatcher.handle_fix_forward(**kwargs)

        self.assertEqual(self.target_file.read_text(encoding="utf-8"), "tier 3 rewrite\n")
        mock_log_tech_debt.assert_not_called()

    @mock.patch("subprocess.run")
    @mock.patch("scripts.tier3_escalate.escalate", autospec=True)
    @mock.patch("scripts.dispatcher.run_build")
    @mock.patch("scripts.tech_debt.log_tech_debt")
    def test_handle_fix_forward_failed_rebuild(self, mock_log_tech_debt, mock_run_build, mock_escalate, mock_run):
        self.target_file.write_text("original content\n", encoding="utf-8")
        
        def mock_escalate_side_effect(*args, **kwargs):
            self.target_file.write_text("tier 3 rewrite\n", encoding="utf-8")
            return {"status": "fix_applied"}
            
        mock_escalate.side_effect = mock_escalate_side_effect
        mock_run_build.return_value = (False, "build failed")
        mock_run.return_value = SimpleNamespace(returncode=0, stdout="diff content", stderr="")

        import inspect
        sig = inspect.signature(dispatcher.handle_fix_forward)
        kwargs = {}
        param_mapping = {
            "task_id": "task-test",
            "target": str(self.target_file),
            "snapshot": "original content\n",
            "build_cmd": "echo 'built'",
            "workdir": self.project_dir,
            "description": "Test description",
            "context_blob": "",
            "revision_note": "",
            "refactor_instruction": "",
            "state": {
                "run_id": "run-test",
                "project_dir": self.project_dir,
                "status": "planned",
                "breakdown": {"phases": []},
                "results": [],
            },
            "item": {
                "description": "Test description",
                "target": str(self.target_file.relative_to(self.project_dir)),
                "build_cmd": "echo 'built'",
            }
        }
        for name in sig.parameters:
            if name in param_mapping:
                kwargs[name] = param_mapping[name]

        dispatcher.handle_fix_forward(**kwargs)

        self.assertEqual(self.target_file.read_text(encoding="utf-8"), "original content\n")
        mock_log_tech_debt.assert_called_once()


class TechDebtTests(unittest.TestCase):
    def test_log_tech_debt_creates_backlog_file_with_hashed_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "module.py"
            target.write_text("print('hi')\n", encoding="utf-8")
            backlog = Path(tmp) / "knowledge" / "TECH_DEBT.md"
            with mock.patch.object(tech_debt, "TECH_DEBT_PATH", backlog):
                tech_debt.log_tech_debt(str(target), "tier 3 could not rebuild")

            expected_hash = hashlib.sha256(target.read_bytes()).hexdigest()
            text = backlog.read_text(encoding="utf-8")
            self.assertIn("# Tech Debt", text)
            self.assertIn(
                f"- [ ] FILE: {target} | HASH: {expected_hash} | REASON: tier 3 could not rebuild",
                text,
            )

    def test_check_staleness_false_when_file_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "unchanged.py"
            target.write_text("v1\n", encoding="utf-8")
            entry = {
                "filepath": str(target),
                "hash": hashlib.sha256(target.read_bytes()).hexdigest(),
                "reason": "test",
            }
            self.assertFalse(tech_debt.check_staleness(entry))

    def test_check_staleness_true_when_file_modified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "modified.py"
            target.write_text("v1\n", encoding="utf-8")
            entry = {
                "filepath": str(target),
                "hash": hashlib.sha256(target.read_bytes()).hexdigest(),
                "reason": "test",
            }
            target.write_text("v2\n", encoding="utf-8")
            self.assertTrue(tech_debt.check_staleness(entry))

    def test_check_staleness_true_when_file_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "deleted.py"
            target.write_text("v1\n", encoding="utf-8")
            entry = {
                "filepath": str(target),
                "hash": hashlib.sha256(target.read_bytes()).hexdigest(),
                "reason": "test",
            }
            target.unlink()
            self.assertTrue(tech_debt.check_staleness(entry))

    def test_cmd_tech_debt_builds_synthetic_state_and_skips_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fresh = Path(tmp) / "fresh.py"
            fresh.write_text("v1\n", encoding="utf-8")
            stale = Path(tmp) / "stale.py"
            stale.write_text("v1\n", encoding="utf-8")
            backlog = Path(tmp) / "knowledge" / "TECH_DEBT.md"
            with mock.patch.object(tech_debt, "TECH_DEBT_PATH", backlog):
                tech_debt.log_tech_debt(str(fresh), "retry me")
                tech_debt.log_tech_debt(str(stale), "stale me")
            stale.write_text("changed\n", encoding="utf-8")

            state = {
                "run_id": "tech-debt-run",
                "project_dir": tmp,
                "status": "planned",
                "prompt": "",
                "plan_text": None,
                "breakdown": {"phases": []},
                "results": [],
            }
            captured: list[dict] = []

            def _fake_dispatch(*args, **kwargs):
                if args:
                    dispatched = args[0]
                elif "state" in kwargs:
                    dispatched = kwargs["state"]
                else:
                    dispatched = next(iter(kwargs.values()))
                captured.append(dispatched)
                return dispatched

            with (
                mock.patch.object(tech_debt, "TECH_DEBT_PATH", backlog),
                mock.patch.object(triapi, "tech_debt", tech_debt, create=True),
                mock.patch.object(triapi.dispatcher, "new_run", return_value=state),
                mock.patch.object(triapi.dispatcher, "save_run"),
                mock.patch.object(
                    triapi.dispatcher, "dispatch", side_effect=_fake_dispatch
                ) as dispatch_mock,
                mock.patch.object(
                    triapi.resource_guard, "pause_services", return_value=[]
                ),
                mock.patch.object(triapi.resource_guard, "resume_services"),
                mock.patch.object(
                    triapi.resource_guard,
                    "unload_other_ollama_models",
                    return_value=[],
                ),
                mock.patch.object(
                    triapi, "load_resource_guard_services", return_value=[]
                ),
                mock.patch.object(
                    triapi, "load_unload_ollama_models_flag", return_value=False
                ),
                mock.patch("sys.stdout", io.StringIO()),
            ):
                triapi.cmd_tech_debt(tmp)

            dispatch_mock.assert_called_once()
            dispatched_state = captured[0]
            self.assertEqual(dispatched_state["status"], "planned")
            items = [
                item
                for phase in dispatched_state["breakdown"]["phases"]
                for item in phase["items"]
            ]
            project_dir = Path(dispatched_state.get("project_dir", ".")).resolve()
            targets = []
            for item in items:
                target = Path(item["target"])
                if not target.is_absolute():
                    target = project_dir / target
                targets.append(str(target.resolve()))
            self.assertIn(str(Path(fresh).resolve()), targets)
            self.assertNotIn(str(Path(stale).resolve()), targets)


class ApplyEditBlocksTests(unittest.TestCase):
    def test_apply_edit_blocks_with_none_returns_none_string(self) -> None:
        original = "line1\nline2\nline3"
        result = edit_blocks.apply_edit_blocks(original, None)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIsNone(result[0])
        self.assertIsInstance(result[1], str)

    def test_apply_edit_blocks_with_empty_string_returns_none_string(self) -> None:
        original = "line1\nline2\nline3"
        result = edit_blocks.apply_edit_blocks(original, "")
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIsNone(result[0])
        self.assertIsInstance(result[1], str)


def test_escalate_with_null_content_returns_failure_and_preserves_file(tmp_path):
    target = tmp_path / "target.py"
    target.write_text("original\n", encoding="utf-8")
    original_bytes = target.read_bytes()

    mock_response = mock.Mock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": None}, "finish_reason": "stop"}],
        "usage": {"prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 10, "completion_tokens": 0}
    }
    mock_response.raise_for_status = mock.Mock()

    with (
        mock.patch.object(tier3_escalate, "load_secrets", return_value={"deepseek_apikey": "test-key"}),
        mock.patch.object(llm_client.requests, "post", return_value=mock_response) as mock_post,
    ):
        result = tier3_escalate.escalate(
            task_id="test-task",
            target=str(target),
            description="test task",
            context_blob="",
            revision_note="",
        )

    mock_post.assert_called_once()
    assert isinstance(result, dict)
    assert "status" in result
    assert result["status"] == "fix_rejected"
    assert target.read_bytes() == original_bytes


if __name__ == "__main__":
    unittest.main()
