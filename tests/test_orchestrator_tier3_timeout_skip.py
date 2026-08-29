"""Tests for orchestrator tier 3 timeout handling (soft-escalate to Tier 2)."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import orchestrator, tier3_escalate


class Tier3EscalateTimeoutTests(unittest.TestCase):
    def test_timeout_returns_timeout_status_not_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target.py"
            target.write_text("original\n", encoding="utf-8")
            with mock.patch.object(
                tier3_escalate.llm_client,
                "execute_llm",
                side_effect=subprocess.TimeoutExpired(cmd=["agy", "-p"], timeout=600),
            ):
                result = tier3_escalate.escalate(
                    "task-1", str(target), context_blob="ctx", description="desc"
                )
        self.assertEqual(result["status"], "timeout")
        self.assertNotEqual(result["status"], "error")
        reason = result.get("reason")
        self.assertTrue(reason)
        self.assertIn("timed out", reason)


class Tier3EscalateCalledProcessErrorTests(unittest.TestCase):
    def test_called_process_error_returns_fix_rejected_not_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target.py"
            target.write_text("original\n", encoding="utf-8")
            with mock.patch.object(
                tier3_escalate.llm_client,
                "execute_llm",
                side_effect=subprocess.CalledProcessError(
                    0, ["agy", "-p"], "", "agy prompt too large for argv: 150000 chars (limit 100000)"
                ),
            ):
                result = tier3_escalate.escalate(
                    "task-1", str(target), context_blob="ctx", description="desc"
                )
        self.assertEqual(result["status"], "fix_rejected")
        self.assertNotEqual(result["status"], "error")
        reason = result.get("reason")
        self.assertTrue(reason)
        self.assertIn("Tier 3 CLI call failed", reason)


class OrchestratorTier3TimeoutSoftEscalateTests(unittest.TestCase):
    def test_tier3_timeout_soft_escalates_to_tier2(self) -> None:
        config = {
            "tier_4_worker": {"build_commands": ["true"]},
            "tier_1_manager": {"enabled": True},
            "critique": {"enabled": False},
        }
        tier4_run = mock.Mock(return_value={"status": "escalate", "consecutive_failures": 2})
        tier3_escalate_mock = mock.Mock(
            return_value={
                "status": "timeout",
                "reason": "Tier 3 request timed out after 600s",
            }
        )
        tier2_escalate_mock = mock.Mock(return_value={"status": "fix_applied"})
        with tempfile.TemporaryDirectory() as tmp:
            target = str(Path(tmp) / "target.py")
            with (
                mock.patch.object(orchestrator, "load_tiers", return_value=config),
                mock.patch.object(orchestrator, "build_context_blob", return_value="ctx"),
                mock.patch.object(orchestrator, "tier4_run", new=tier4_run),
                mock.patch.object(
                    orchestrator, "check_tier3_peak_hours_ok", return_value={"ok": True}
                ),
                mock.patch.object(orchestrator, "tier3_escalate", new=tier3_escalate_mock),
                mock.patch.object(orchestrator, "check_tier2_ok", return_value={"ok": True}),
                mock.patch.object(orchestrator, "tier2_escalate", new=tier2_escalate_mock),
                mock.patch.object(orchestrator, "_rebuild_after_patch", return_value=True),
                mock.patch.object(orchestrator, "read_state", return_value={}),
                mock.patch.object(orchestrator, "report", return_value={}),
                mock.patch.object(orchestrator, "human_handoff") as human_handoff_mock,
            ):
                result = orchestrator.run_task(
                    "task-t3-timeout", "fix it", target, workdir=tmp, build_cmd="true"
                )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["resolved_by"], "tier_2")
        tier2_escalate_mock.assert_called_once()
        human_handoff_mock.assert_not_called()
