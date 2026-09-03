import io
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from scripts import budget_guard, jules_client, triapi


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