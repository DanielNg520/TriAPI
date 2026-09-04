"""Unit tests verifying orchestrator.run_task threads context_blob through
every tier function and that the tiers no longer make independent keyword
searches (the previously-reimplemented lessons.select_relevant call inside
the tier prompt builders)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Make sure the repo root is importable.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts import (
    lessons,
    orchestrator,
    tier1_escalate,
    tier2_escalate,
    tier3_escalate,
    tier4_worker,
)


# A tiny baseline tiers.yaml so load_tiers() / resolve_deepseek_tier() work
# without depending on the real config file. The tests below mock out the
# external LLM/build calls anyway, so the exact contents mostly just need
# to be parseable.
MINIMAL_TIERS_CONFIG: dict = {
    "tier_4_worker": {
        "provider": "ollama",
        "endpoint": "http://localhost:11434",
        "models": {"default": "local-model"},
        "default_model": "default",
        "build_commands": ["true"],
    },
    "tier_3_debugger": {
        "provider": "deepseek",
        "endpoint": "http://example.invalid",
        "api_key_secret": "open_router_api_key",
        "models": {"default": "deepseek-model"},
        "default_model": "default",
    },
    "tier_2_manager": {
        "provider": "openrouter",
        "endpoint": "http://example.invalid",
        "api_key_secret": "open_router_api_key",
        "models": {"default": "nemotron-model"},
        "default_model": "default",
    },
    "tier_1_manager": {
        "provider": "cli",
        "models": {"default": "claude-code"},
        "default_model": "default",
    },
    "escalation_rules": {
        "tier4_to_tier3": {"threshold": 1},
        "tier3_to_tier2": {"threshold": 1},
        "tier2_to_tier1": {"threshold": 1},
        "tier1_to_handoff": {"threshold": 1},
    },
    "memory_rag": {"enabled": False},
    "critique": {"enabled": False},
}


def _make_state_dir(tmp: Path) -> Path:
    state_dir = tmp / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


class ContextBlobThreadingTests(unittest.TestCase):
    """orchestrator.run_task must thread a single context_blob through to
    every tier function it calls, instead of letting each tier build its
    own blob independently."""

    def setUp(self) -> None:
        self._tmp_ctx = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp_ctx.cleanup)
        self.tmp = Path(self._tmp_ctx.name)

        # Redirect all the path-based side effects orchestrator performs to
        # the temp dir so we don't litter the real repo with state/escalation
        # files.
        self.state_dir = _make_state_dir(self.tmp)
        self.escalations_dir = self.tmp / "logs"
        self.escalations_dir.mkdir(parents=True, exist_ok=True)
        self.escalations_log = self.escalations_dir / "escalations.jsonl"

        self._path_patches = [
            mock.patch.object(orchestrator, "ESCALATIONS_LOG", self.escalations_log),
            mock.patch.object(orchestrator, "ESCALATIONS_DIR", self.escalations_dir),
            mock.patch.object(tier4_worker, "COST_LOG_PATH", self.tmp / "cost.jsonl"),
            mock.patch.object(tier3_escalate, "COST_LOG_PATH", self.tmp / "cost.jsonl"),
            mock.patch.object(tier2_escalate, "COST_LOG_PATH", self.tmp / "cost.jsonl"),
            mock.patch.object(tier1_escalate, "COST_LOG_PATH", self.tmp / "cost.jsonl"),
            mock.patch.object(tier4_worker, "log_cost", lambda e: None),
            mock.patch.object(tier3_escalate, "log_cost", lambda e: None),
            mock.patch.object(tier2_escalate, "log_cost", lambda e: None),
            mock.patch.object(tier1_escalate, "log_cost", lambda e: None),
            # State module writes JSON next to the script; redirect those too.
        ]
        for p in self._path_patches:
            p.start()
            self.addCleanup(p.stop)

    def _patch_state_module(self) -> None:
        """Redirect scripts.state file paths into our temp dir."""
        state_mod = sys.modules["scripts.state"]
        state_patches = [
            mock.patch.object(state_mod, "STATE_DIR", self.state_dir),
        ]
        for p in state_patches:
            p.start()
            self.addCleanup(p.stop)

    def test_run_task_threads_context_blob_into_tier4(self) -> None:
        """The exact context_blob built by orchestrator (memory-RAG disabled,
        context_files provided) must be passed verbatim to tier4_worker.run."""
        self._patch_state_module()

        context_blob = (
            "Reference file `README.md` (read-only):\n"
            "```\nsome readme content\n```\n"
        )
        rag_context = ""

        with tempfile.TemporaryDirectory() as workdir_ctx:
            workdir = Path(workdir_ctx)
            target = workdir / "code.py"
            target.write_text("print('hi')\n", encoding="utf-8")

            with mock.patch.object(orchestrator, "load_tiers", return_value=MINIMAL_TIERS_CONFIG), \
                 mock.patch.object(orchestrator, "resolve_deepseek_tier", return_value=None), \
                 mock.patch.object(orchestrator, "build_context_blob", return_value=context_blob) as t4_blob, \
                 mock.patch.object(orchestrator, "memory_retrieval") as mem_ret, \
                 mock.patch.object(orchestrator, "tier4_run", return_value={"status": "success", "consecutive_failures": 0}) as t4_run, \
                 mock.patch.object(orchestrator, "clear_state") as clear_state, \
                 mock.patch.object(orchestrator, "report", return_value={}):
                mem_ret.retrieve_context.return_value = rag_context
                result = orchestrator.run_task(
                    task_id="t4-1",
                    description="fix typo",
                    target=str(target),
                    workdir=str(workdir),
                    build_cmd="true",
                    context_files=["README.md"],
                )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["resolved_by"], "tier_4")
        t4_run.assert_called_once()
        # tier4_worker.run is the 7th positional arg, after the 6 leading
        # strings (task_id, description, target, workdir, build_cmd,
        # tier4_model). context_blob is the 7th positional arg.
        args, kwargs = t4_run.call_args
        self.assertEqual(args[6], context_blob)
        # build_context_blob must have been called with exactly the
        # context_files we passed, so no independent re-resolution happens.
        t4_blob.assert_called_once_with(["README.md"], str(workdir))

    def test_run_task_appends_memory_rag_to_context_blob(self) -> None:
        """When memory_rag.enabled is True, the retrieved RAG context must be
        appended to the same context_blob (and that combined blob must be
        what every downstream tier receives)."""
        self._patch_state_module()

        base_blob = "Reference file `README.md` (read-only):\n```\nreadme\n```\n"
        rag_context = "## memory-rag retrieved context\nblessed snippet\n"

        with tempfile.TemporaryDirectory() as workdir_ctx:
            workdir = Path(workdir_ctx)
            target = workdir / "code.py"
            target.write_text("print('hi')\n", encoding="utf-8")

            config = json.loads(json.dumps(MINIMAL_TIERS_CONFIG))
            config["memory_rag"] = {"enabled": True}

            with mock.patch.object(orchestrator, "load_tiers", return_value=config), \
                 mock.patch.object(orchestrator, "resolve_deepseek_tier", return_value=None), \
                 mock.patch.object(orchestrator, "build_context_blob", return_value=base_blob), \
                 mock.patch.object(orchestrator, "memory_retrieval") as mem_ret, \
                 mock.patch.object(orchestrator, "tier4_run", return_value={"status": "success", "consecutive_failures": 0}) as t4_run, \
                 mock.patch.object(orchestrator, "clear_state"), \
                 mock.patch.object(orchestrator, "report", return_value={}):
                mem_ret.retrieve_context.return_value = rag_context
                orchestrator.run_task(
                    task_id="t4-rag",
                    description="fix typo",
                    target=str(target),
                    workdir=str(workdir),
                    build_cmd="true",
                    context_files=["README.md"],
                )

        expected_blob = (base_blob + "\n\n" + rag_context).strip()
        args, _ = t4_run.call_args
        self.assertEqual(args[6], expected_blob)

    def test_run_task_threads_same_blob_to_tier3_after_tier4_escalates(self) -> None:
        """If Tier 4 escalates, the SAME context_blob must be forwarded into
        tier3_escalate.escalate (not rebuilt, not keyword-re-searched)."""
        self._patch_state_module()

        context_blob = (
            "Reference file `README.md` (read-only):\n```\nreadme\n```\n"
        )

        with tempfile.TemporaryDirectory() as workdir_ctx:
            workdir = Path(workdir_ctx)
            target = workdir / "code.py"
            target.write_text("print('hi')\n", encoding="utf-8")
            state_file = self.state_dir / "t4-esc.json"

            with mock.patch.object(orchestrator, "load_tiers", return_value=MINIMAL_TIERS_CONFIG), \
                 mock.patch.object(orchestrator, "resolve_deepseek_tier", return_value=None), \
                 mock.patch.object(orchestrator, "build_context_blob", return_value=context_blob), \
                 mock.patch.object(orchestrator, "memory_retrieval") as mem_ret, \
                 mock.patch.object(orchestrator, "tier4_run", return_value={"status": "escalate", "consecutive_failures": 1, "stderr": "boom"}), \
                 mock.patch.object(orchestrator, "_peak_hour_guard", return_value=None), \
                 mock.patch.object(orchestrator, "check_tier3_peak_hours_ok", return_value={"ok": True}), \
                 mock.patch.object(orchestrator, "tier3_escalate", return_value={"status": "fix_applied"}) as t3_esc, \
                 mock.patch.object(orchestrator, "report", return_value={}), \
                 mock.patch.object(orchestrator, "record_failure") as rec_fail:
                mem_ret.retrieve_context.return_value = ""
                # Pre-populate state file (record_failure normally creates it)
                state_file.write_text(json.dumps({"last_stderr": "boom", "consecutive_failures": 1}))
                result = orchestrator.run_task(
                    task_id="t4-esc",
                    description="fix typo",
                    target=str(target),
                    workdir=str(workdir),
                    build_cmd="true",
                    context_files=["README.md"],
                )

        t3_esc.assert_called_once()
        kwargs = t3_esc.call_args.kwargs
        self.assertEqual(kwargs["context_blob"], context_blob)

    def test_run_task_threads_same_blob_to_tier2_after_tier3_rejects(self) -> None:
        """If Tier 3 returns fix_rejected, the SAME context_blob must be
        forwarded into tier2_escalate.escalate."""
        self._patch_state_module()

        context_blob = "Reference file `README.md` (read-only):\n```\nr\n```\n"

        with tempfile.TemporaryDirectory() as workdir_ctx:
            workdir = Path(workdir_ctx)
            target = workdir / "code.py"
            target.write_text("print('hi')\n", encoding="utf-8")
            state_file = self.state_dir / "t3-rej.json"
            state_file.write_text(json.dumps({"last_stderr": "boom", "consecutive_failures": 2}))

            with mock.patch.object(orchestrator, "load_tiers", return_value=MINIMAL_TIERS_CONFIG), \
                 mock.patch.object(orchestrator, "resolve_deepseek_tier", return_value=None), \
                 mock.patch.object(orchestrator, "build_context_blob", return_value=context_blob), \
                 mock.patch.object(orchestrator, "memory_retrieval") as mem_ret, \
                 mock.patch.object(orchestrator, "tier4_run", return_value={"status": "escalate", "consecutive_failures": 2, "stderr": "boom"}), \
                 mock.patch.object(orchestrator, "check_tier3_peak_hours_ok", return_value={"ok": True}), \
                 mock.patch.object(orchestrator, "tier3_escalate", return_value={"status": "fix_rejected", "reason": "x"}), \
                 mock.patch.object(orchestrator, "tier2_escalate", return_value={"status": "fix_applied"}) as t2_esc, \
                 mock.patch.object(orchestrator, "report", return_value={}), \
                 mock.patch.object(orchestrator, "clear_state"):
                mem_ret.retrieve_context.return_value = ""
                result = orchestrator.run_task(
                    task_id="t3-rej",
                    description="fix typo",
                    target=str(target),
                    workdir=str(workdir),
                    build_cmd="true",
                    context_files=["README.md"],
                )

        t2_esc.assert_called_once()
        self.assertEqual(t2_esc.call_args.kwargs["context_blob"], context_blob)

    def test_run_task_threads_same_blob_to_tier1_after_tier2_rejects(self) -> None:
        """If Tier 2 returns fix_rejected, the SAME context_blob must be
        forwarded into tier1_escalate.escalate."""
        self._patch_state_module()

        context_blob = "Reference file `README.md` (read-only):\n```\nr\n```\n"

        with tempfile.TemporaryDirectory() as workdir_ctx:
            workdir = Path(workdir_ctx)
            target = workdir / "code.py"
            target.write_text("print('hi')\n", encoding="utf-8")
            state_file = self.state_dir / "t2-rej.json"
            state_file.write_text(json.dumps({"last_stderr": "boom", "consecutive_failures": 3}))

            with mock.patch.object(orchestrator, "load_tiers", return_value=MINIMAL_TIERS_CONFIG), \
                 mock.patch.object(orchestrator, "resolve_deepseek_tier", return_value=None), \
                 mock.patch.object(orchestrator, "build_context_blob", return_value=context_blob), \
                 mock.patch.object(orchestrator, "memory_retrieval") as mem_ret, \
                 mock.patch.object(orchestrator, "tier4_run", return_value={"status": "escalate", "consecutive_failures": 3, "stderr": "boom"}), \
                 mock.patch.object(orchestrator, "check_tier3_peak_hours_ok", return_value={"ok": True}), \
                 mock.patch.object(orchestrator, "tier3_escalate", return_value={"status": "fix_rejected", "reason": "x"}), \
                 mock.patch.object(orchestrator, "tier2_escalate", return_value={"status": "fix_rejected", "reason": "x"}), \
                 mock.patch.object(orchestrator, "tier1_escalate", return_value={"status": "fix_applied"}) as t1_esc, \
                 mock.patch.object(orchestrator, "report", return_value={}), \
                 mock.patch.object(orchestrator, "clear_state"):
                mem_ret.retrieve_context.return_value = ""
                result = orchestrator.run_task(
                    task_id="t2-rej",
                    description="fix typo",
                    target=str(target),
                    workdir=str(workdir),
                    build_cmd="true",
                    context_files=["README.md"],
                )

        t1_esc.assert_called_once()
        self.assertEqual(t1_esc.call_args.kwargs["context_blob"], context_blob)

    def test_run_task_threads_combined_blob_into_librarian_doc_path(self) -> None:
        """When the target matches tier_5_librarian.target_globs, the
        combined blob must be folded into the description passed to
        librarian_escalate.run (since librarian.run has no context_blob
        parameter)."""
        self._patch_state_module()

        base_blob = "Reference file `README.md` (read-only):\n```\nr\n```\n"
        rag_context = "rag snippet\n"
        combined_blob = (base_blob + "\n\n" + rag_context).strip()
        original_description = "update the docs"

        with tempfile.TemporaryDirectory() as workdir_ctx:
            workdir = Path(workdir_ctx)
            target = workdir / "AGENTS.md"
            target.write_text("# agents\n", encoding="utf-8")

            config = json.loads(json.dumps(MINIMAL_TIERS_CONFIG))
            config["tier_5_librarian"] = {
                "enabled": True,
                "target_globs": ["*.md"],
            }
            config["memory_rag"] = {"enabled": True}

            with mock.patch.object(orchestrator, "load_tiers", return_value=config), \
                 mock.patch.object(orchestrator, "resolve_deepseek_tier", return_value=None), \
                 mock.patch.object(orchestrator, "build_context_blob", return_value=base_blob), \
                 mock.patch.object(orchestrator, "memory_retrieval") as mem_ret, \
                 mock.patch.object(orchestrator.librarian_escalate, "run", return_value={"status": "success", "resolved_by": "tier_5"}) as lib_run, \
                 mock.patch.object(orchestrator, "report", return_value={}):
                mem_ret.retrieve_context.return_value = rag_context
                result = orchestrator.run_task(
                    task_id="lib-1",
                    description=original_description,
                    target=str(target),
                    workdir=str(workdir),
                    build_cmd="true",
                    context_files=["README.md"],
                )

        lib_run.assert_called_once()
        # The description passed to librarian.run must contain the
        # combined blob (base + rag) since librarian.run() has no
        # context_blob parameter.
        args = lib_run.call_args.args
        passed_description = args[1]
        self.assertIn(combined_blob, passed_description)
        # And the original description must still be present (prefixed).
        self.assertTrue(passed_description.startswith(original_description))


class TierNoLongerIndependentKeywordSearchTests(unittest.TestCase):
    """The tier prompt builders (tier3.build_stable_context, tier2's
    build_user_content, tier1.build_prompt) must NOT independently call
    lessons.select_relevant() -- context selection is the orchestrator's
    job and is already inside the threaded context_blob."""

    def test_tier3_build_stable_context_does_not_call_select_relevant(self) -> None:
        captured: list = []
        with mock.patch.object(
            tier3_escalate.lessons,
            "select_relevant",
            side_effect=lambda *a, **kw: captured.append((a, kw)) or [],
        ):
            tier3_escalate.build_stable_context(
                target_path=Path("/tmp/whatever.py"),
                context_blob="some blob",
                current_contents="x = 1\n",
                description="fix it",
            )
        self.assertEqual(captured, [])

    def test_tier2_build_user_content_does_not_call_select_relevant(self) -> None:
        captured: list = []
        with mock.patch.object(
            tier2_escalate.lessons,
            "select_relevant",
            side_effect=lambda *a, **kw: captured.append((a, kw)) or [],
        ):
            tier2_escalate.build_user_content(
                target_path=Path("/tmp/whatever.py"),
                stderr="boom",
                context_blob="some blob",
                revision_note="",
                current_contents="x = 1\n",
                description="fix it",
            )
        self.assertEqual(captured, [])

    def test_tier1_build_prompt_does_not_call_select_relevant(self) -> None:
        captured: list = []
        with mock.patch.object(
            tier1_escalate.lessons,
            "select_relevant",
            side_effect=lambda *a, **kw: captured.append((a, kw)) or [],
        ):
            tier1_escalate.build_prompt(
                target_path=Path("/tmp/whatever.py"),
                stderr="boom",
                context_blob="some blob",
                revision_note="",
                current_contents="x = 1\n",
                description="fix it",
            )
        self.assertEqual(captured, [])

    def test_lessons_select_relevant_is_not_invoked_from_tier_prompts(self) -> None:
        """Integration check: a sweep across all tier prompt builders must
        produce zero calls to lessons.select_relevant -- the previously-
        implemented per-tier keyword search is gone."""
        captured: list = []
        with mock.patch.object(
            lessons,
            "select_relevant",
            side_effect=lambda *a, **kw: captured.append(("select_relevant", a, kw)) or [],
        ):
            tier3_escalate.build_stable_context(
                target_path=Path("/tmp/whatever.py"),
                context_blob="blob",
                current_contents="x = 1\n",
                description="fix it",
            )
            tier2_escalate.build_user_content(
                target_path=Path("/tmp/whatever.py"),
                stderr="boom",
                context_blob="blob",
                revision_note="",
                current_contents="x = 1\n",
                description="fix it",
            )
            tier1_escalate.build_prompt(
                target_path=Path("/tmp/whatever.py"),
                stderr="boom",
                context_blob="blob",
                revision_note="",
                current_contents="x = 1\n",
                description="fix it",
            )
        select_relevant_calls = [c for c in captured if c[0] == "select_relevant"]
        self.assertEqual(select_relevant_calls, [])

    def test_tier3_build_stable_context_preserves_context_blob_verbatim(self) -> None:
        """Whatever blob the orchestrator threads in must arrive in the
        returned prompt unchanged -- no re-extraction, no keyword filter."""
        blob = "Reference file `X.md`:\n```\ncontent\n```\n"
        result = tier3_escalate.build_stable_context(
            target_path=Path("/tmp/whatever.py"),
            context_blob=blob,
            current_contents="x = 1\n",
            description="fix it",
        )
        self.assertIn(blob, result)

    def test_tier2_build_user_content_preserves_context_blob_verbatim(self) -> None:
        blob = "Reference file `X.md`:\n```\ncontent\n```\n"
        result = tier2_escalate.build_user_content(
            target_path=Path("/tmp/whatever.py"),
            stderr="boom",
            context_blob=blob,
            revision_note="",
            current_contents="x = 1\n",
            description="fix it",
        )
        self.assertIn(blob, result)

    def test_tier1_build_prompt_preserves_context_blob_verbatim(self) -> None:
        blob = "Reference file `X.md`:\n```\ncontent\n```\n"
        result = tier1_escalate.build_prompt(
            target_path=Path("/tmp/whatever.py"),
            stderr="boom",
            context_blob=blob,
            revision_note="",
            current_contents="x = 1\n",
            description="fix it",
        )
        self.assertIn(blob, result)
