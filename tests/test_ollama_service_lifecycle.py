"""Regression tests for Ollama service lifecycle."""

from __future__ import annotations

import unittest
from unittest import mock

from scripts import triapi


class CmdDispatchOllamaLifecycleTests(unittest.TestCase):
    def test_cmd_dispatch_restores_ollama_state_on_exception(self) -> None:
        state = {
            "run_id": "run-1",
            "status": "planned",
            "plan_text": "approved",
            "project_dir": "/tmp/project-dir",
        }

        def fail_dispatch(_state):
            raise RuntimeError("dispatch crash")

        snapshot = {"ollama_state": "saved"}

        with (
            mock.patch.object(triapi.dispatcher, "load_run", return_value=state),
            mock.patch.object(triapi.resource_guard, "pause_services", return_value=["svc"]),
            mock.patch.object(triapi.resource_guard, "resume_services"),
            mock.patch.object(triapi.resource_guard, "snapshot_ollama_state", return_value=snapshot),
            mock.patch.object(
                triapi.resource_guard, "restore_ollama_state"
            ) as restore_ollama_state,
            mock.patch.object(triapi, "load_resource_guard_services", return_value=[]),
            mock.patch.object(
                triapi,
                "load_tiers",
                return_value={
                    "self_fix": {"enabled": True},
                    "tier_4_worker": {"endpoint": "http://localhost:11434", "provider": "ollama"},
                },
            ),
            mock.patch.object(triapi, "_breakdown_and_dispatch", side_effect=fail_dispatch),
            mock.patch.object(triapi.self_fix, "capture_crash"),
            mock.patch.object(triapi.self_fix, "queue_self_fix"),
        ):
            with self.assertRaisesRegex(RuntimeError, "dispatch crash"):
                triapi.cmd_dispatch(state["run_id"], background=False)

        restore_ollama_state.assert_called_once_with(snapshot, ollama_host="http://localhost:11434")
