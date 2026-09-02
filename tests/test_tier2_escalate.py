"""Tests for Tier 2: Escalation client (Nemotron via OpenRouter).

Called after Tier 1 (Claude Code CLI) fails to resolve the build -- the
final automated tier before human handoff. Mirrors tier3_escalate.py's
structure: budget guard checks, model selection, edit block application,
code extraction, cost logging, and content validation.

Must only be used after budget_guard.check_tier2_ok() passes -- Google
AI Studio's free tier is rate-limited, not unlimited, and this must never
silently run into paid overage.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

import pytest

from scripts.budget_guard import check_tier2_ok
from scripts.tier2_escalate import escalate
from scripts import content_guard, edit_blocks, llm_client
from scripts.config_loader import load_tiers
from scripts.secrets_loader import load_secrets
from scripts.state import read_state


class TestEscalate:
    """Tests for the escalate function, excluding fallback_chain loop tests."""

    def test_escalate_skipped_when_budget_guard_fails(self) -> None:
        """Tier 2 should be skipped if budget guard fails.

        check_tier2_ok() must be mocked explicitly -- it reads a local
        usage log, not a network call, so it never raises and its real
        pass/fail outcome depends on incidental prior usage in this
        environment, not anything this test controls."""
        with mock.patch(
            "scripts.tier2_escalate.check_tier2_ok",
            return_value={"ok": False, "reason": "would exceed free-tier RPD limit (250/250 in the last 24h)"},
        ):
            result = escalate("task-2", "scripts/test_target.py")
        assert result["status"] == "skipped"
        assert "rpd limit" in result["reason"].lower()

    def test_escalate_edit_block_application(self) -> None:
        """Test that edit blocks are applied correctly when file exists."""
        target = Path("/tmp/test_fix.py")
        target.write_text("def broken():\n    pass\n", encoding="utf-8")
        try:
            with mock.patch(
                "scripts.tier2_escalate.check_tier2_ok", return_value={"ok": True, "reason": ""}
            ):
                with mock.patch(
                    "scripts.tier2_escalate.llm_client.execute_llm"
                ) as mock_exec:
                    mock_exec.return_value = (
                        "def fixed():\n    pass\n",
                        "standard",
                        100,
                        200,
                    )
                    result = escalate("task-3", str(target), model="pro")
            assert result["status"] == "fix_applied"
            assert target.read_text(encoding="utf-8") == "def fixed():\n    pass\n"
        finally:
            target.unlink(missing_ok=True)

    def test_escalate_extract_code_from_response(self) -> None:
        """Test code extraction from LLM response when no existing file."""
        target = Path("/tmp/test_new_file.py")
        target.unlink(missing_ok=True)
        try:
            with mock.patch(
                "scripts.tier2_escalate.check_tier2_ok", return_value={"ok": True, "reason": ""}
            ):
                with mock.patch(
                    "scripts.tier2_escalate.llm_client.execute_llm"
                ) as mock_exec:
                    mock_exec.return_value = (
                        "```python\ndef fixed():\n    pass\n```",
                        "standard",
                        100,
                        200,
                    )
                    result = escalate("task-4", str(target), model="pro")
            assert result["status"] == "fix_applied"
            assert target.read_text(encoding="utf-8") == "def fixed():\n    pass\n"
        finally:
            target.unlink(missing_ok=True)

    def test_escalate_skipped_on_synthetic_called_process_error_argv_limit(self) -> None:
        import subprocess
        target = Path("/tmp/test_synthetic_error.py")
        target.write_text("def broken():\n    pass\n", encoding="utf-8")
        try:
            with mock.patch("scripts.tier2_escalate.check_tier2_ok", return_value={"ok": True, "reason": ""}):
                with mock.patch("scripts.tier2_escalate.llm_client.execute_llm") as mock_exec:
                    mock_exec.side_effect = subprocess.CalledProcessError(
                        0, ["agy", "-p", "<omitted>"], "", "agy prompt too large for argv"
                    )
                    result = escalate("task-5", str(target), model="pro")
            assert result["status"] == "skipped"
        finally:
            target.unlink(missing_ok=True)

    def test_escalate_skipped_on_synthetic_called_process_error_json_decode(self) -> None:
        import subprocess
        target = Path("/tmp/test_synthetic_error2.py")
        target.write_text("def broken():\n    pass\n", encoding="utf-8")
        try:
            with mock.patch("scripts.tier2_escalate.check_tier2_ok", return_value={"ok": True, "reason": ""}):
                with mock.patch("scripts.tier2_escalate.llm_client.execute_llm") as mock_exec:
                    mock_exec.side_effect = subprocess.CalledProcessError(
                        0, ["agy", "-p", "prompt"], "invalid json", "stderr passthrough"
                    )
                    result = escalate("task-6", str(target), model="pro")
            assert result["status"] == "skipped"
        finally:
            target.unlink(missing_ok=True)

    def test_escalate_skipped_on_synthetic_called_process_error_status_not_success(self) -> None:
        import subprocess
        target = Path("/tmp/test_synthetic_error3.py")
        target.write_text("def broken():\n    pass\n", encoding="utf-8")
        try:
            with mock.patch("scripts.tier2_escalate.check_tier2_ok", return_value={"ok": True, "reason": ""}):
                with mock.patch("scripts.tier2_escalate.llm_client.execute_llm") as mock_exec:
                    mock_exec.side_effect = subprocess.CalledProcessError(
                        0, ["agy", "-p", "prompt"], '{"status": "ERROR"}', "agy status='ERROR' stderr_tail='some error'"
                    )
                    result = escalate("task-7", str(target), model="pro")
            assert result["status"] == "skipped"
        finally:
            target.unlink(missing_ok=True)

    def test_escalate_soft_escalates_on_genuine_called_process_error(self) -> None:
        # Real incident 2026-09-02: a genuinely non-zero-exit agy CLI
        # failure previously returned "error", which orchestrator.run_task
        # treats as fatal (raises RuntimeError, crashing the whole `triapi
        # dispatch` process) instead of soft-escalating to Tier 1 -- the
        # same crash-vs-soft-escalate distinction tier3_escalate.py's own
        # CalledProcessError handling already got right (fixed 2026-08-29).
        # "fix_rejected" is what orchestrator.py's Tier 2 block logs and
        # falls through on, matching that existing pattern.
        import subprocess
        target = Path("/tmp/test_genuine_error.py")
        target.write_text("def broken():\n    pass\n", encoding="utf-8")
        try:
            with mock.patch("scripts.tier2_escalate.check_tier2_ok", return_value={"ok": True, "reason": ""}):
                with mock.patch("scripts.tier2_escalate.llm_client.execute_llm") as mock_exec:
                    mock_exec.side_effect = subprocess.CalledProcessError(
                        1, ["agy", "-p", "prompt"], "", "real failure"
                    )
                    result = escalate("task-8", str(target), model="pro")
            assert result["status"] == "fix_rejected"
        finally:
            target.unlink(missing_ok=True)
