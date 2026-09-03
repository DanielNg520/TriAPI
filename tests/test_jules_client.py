import unittest
from unittest import mock

from scripts import jules_client


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