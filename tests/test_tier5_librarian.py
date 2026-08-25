"""Regression tests for the Tier 5 (librarian) doc-fix pipeline.

Split out of test_branch_features.py (2026-08-24): that file was already at
the 73728-char Tier 4 context ceiling (content_guard.check_write's
MAX_WRITE_CHARS), so appending a whole new TestTier5Librarian class there
would have authored a file Tier 4 could never edit again. See
scripts/content_guard.py's own docstring for why that's a one-way door.

Every test here patches strictly at the HTTP boundary (llm_client.requests)
or at the module-function boundary already used elsewhere in this suite
(mirrors LlmClientOpenAIErrorBodyTests / the tier1-3 escalate tests in
test_branch_features.py) -- zero real network calls, including to a local
Ollama daemon or OpenRouter.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from scripts import (
    config_loader,
    content_guard,
    dispatcher,
    librarian_escalate,
    llm_client,
    lessons,
    orchestrator,
    tier1_escalate,
    tier2_escalate,
    tier3_escalate,
)


def _fake_response(content: str, prompt_tokens: int = 5, completion_tokens: int = 3) -> mock.Mock:
    resp = mock.Mock()
    resp.raise_for_status = mock.Mock()
    resp.json.return_value = {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
    }
    return resp


class TestTier5Librarian(unittest.TestCase):
    def _tier5_config(self) -> dict:
        return {
            "tier_5_librarian": {
                "enabled": True,
                "role": "doc_librarian",
                "provider": "ollama",
                "models": {
                    "primary": "mistral-small:latest",
                    "fallback_local": "ollama_fallback",
                    "fallback_openrouter": "stealth/ox-alpha",
                },
                "target_globs": ["*.md", "docs/**"],
                "verify_command": None,
                "max_attempts": 2,
            },
            "ollama_fallback": {
                "endpoint": "http://localhost:11434",
                "models": {"default": "qwen2.5-coder:14b-instruct-q6_K"},
            },
            "tier_1_planner": {"endpoint": "https://openrouter.ai/api/v1"},
            "escalation_rules": {
                "tier5_to_fallbacks": {
                    "threshold": 2,
                    "chain": ["fallback_local", "fallback_openrouter", "log_and_notify"],
                }
            },
        }

    def _secrets(self) -> dict:
        return {"ollama_host": "http://localhost:11434", "open_router_api_key": "fake-key"}

    # -- (1) config schema ---------------------------------------------

    def test_load_tiers_exposes_tier_5_librarian_block(self) -> None:
        config = config_loader.load_tiers()
        self.assertIn("tier_5_librarian", config)
        self.assertIn("primary", config["tier_5_librarian"]["models"])

    def test_load_tiers_raises_when_tier_5_librarian_missing(self) -> None:
        with open(config_loader.TIERS_PATH, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        raw.pop("tier_5_librarian")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp) / "tiers.yaml"
            tmp_path.write_text(yaml.dump(raw), encoding="utf-8")
            with self.assertRaises(ValueError):
                config_loader.load_tiers(path=tmp_path)

    # -- (2) is_doc_target glob truth table ------------------------------

    def test_is_doc_target_glob_truth_table(self) -> None:
        globs = self._tier5_config()["tier_5_librarian"]["target_globs"]
        cases = [
            ("README.md", True),
            ("AGENTS.md", True),
            ("notes.MD", True),  # case-insensitive
            ("docs/guide.rst", True),
            ("docs/sub/deep/file.txt", True),
            ("src/main.cpp", False),
            ("scripts/dispatcher.py", False),
            ("", False),
        ]
        for rel_path, expected in cases:
            with self.subTest(rel_path=rel_path):
                self.assertEqual(dispatcher.is_doc_target(rel_path, globs), expected)
        self.assertFalse(dispatcher.is_doc_target("README.md", []))

    # -- (3) detect_email_like_content ----------------------------------

    def test_detect_email_like_content_finds_address_and_mailto(self) -> None:
        text = "Reach the maintainer at foo@example.com or via mailto:bar@example.org"
        findings = llm_client.detect_email_like_content(text)
        self.assertTrue(any(f["snippet"] == "foo@example.com" for f in findings))
        self.assertTrue(any(f["snippet"] == "mailto:" for f in findings))

    def test_detect_email_like_content_clean_text_returns_empty(self) -> None:
        self.assertEqual(
            llm_client.detect_email_like_content("This changelog has no contact info at all."),
            [],
        )

    # -- (4) success path -------------------------------------------------

    def test_success_path_lands_via_edit_block_with_local_billing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "docs" / "GUIDE.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# Guide\n\nOld sentence here.\n", encoding="utf-8")
            cost_log = Path(tmp) / "cost_log.jsonl"

            response = (
                "<<<<<<< SEARCH\n"
                "Old sentence here.\n"
                "=======\n"
                "New sentence here.\n"
                ">>>>>>> REPLACE\n"
            )

            with (
                mock.patch.object(librarian_escalate, "load_tiers", return_value=self._tier5_config()),
                mock.patch.object(librarian_escalate, "load_secrets", return_value=self._secrets()),
                mock.patch.object(librarian_escalate, "COST_LOG_PATH", cost_log),
                mock.patch.object(
                    librarian_escalate.llm_client, "execute_llm",
                    return_value=(response, "ollama", 12, 7),
                ) as execute_llm,
                mock.patch.object(
                    librarian_escalate.content_guard, "check_write",
                    wraps=content_guard.check_write,
                ) as check_write,
                mock.patch.object(librarian_escalate, "clear_state") as clear_state,
            ):
                result = librarian_escalate.run(
                    "t-success", "keep guide fresh", str(target), workdir=tmp,
                )

            execute_llm.assert_called_once()
            check_write.assert_called_once()
            clear_state.assert_called_once_with("t-success")
            self.assertEqual(target.read_text(encoding="utf-8"), "# Guide\n\nNew sentence here.\n")
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["resolved_by"], "tier_5")
            self.assertTrue(result["changed"])

            cost_lines = cost_log.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(cost_lines), 1)
            cost_entry = json.loads(cost_lines[0])
            self.assertEqual(cost_entry["billing"], "local")

    # -- (5) escalation order + paid-ladder sentinels ----------------------

    def test_escalation_order_is_primary_then_fallback_local_then_openrouter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "docs" / "STALE.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("stale doc\n", encoding="utf-8")

            # Every attempt returns content that fails defensive_json_parse,
            # so the chain runs to full exhaustion through all 3 providers.
            responses = [_fake_response("not JSON, sorry") for _ in range(3)]

            paid_ladder_sentinel = mock.Mock(
                side_effect=AssertionError("paid tier must never be called from tier_5_librarian")
            )

            with (
                mock.patch.object(librarian_escalate, "load_tiers", return_value=self._tier5_config()),
                mock.patch.object(librarian_escalate, "load_secrets", return_value=self._secrets()),
                mock.patch.object(llm_client.requests, "post", side_effect=responses) as post,
                mock.patch.object(llm_client, "_call_claude_cli", new=paid_ladder_sentinel),
                mock.patch.object(llm_client, "_call_gemini_api", new=paid_ladder_sentinel),
                mock.patch.object(tier1_escalate, "escalate", new=paid_ladder_sentinel),
                mock.patch.object(tier2_escalate, "escalate", new=paid_ladder_sentinel),
                mock.patch.object(tier3_escalate, "escalate", new=paid_ladder_sentinel),
                mock.patch.object(
                    orchestrator, "ESCALATIONS_DIR", Path(tmp) / "logs"
                ),
                mock.patch.object(
                    orchestrator, "ESCALATIONS_LOG", Path(tmp) / "logs" / "esc.jsonl"
                ),
                mock.patch.object(lessons, "LESSONS_PATH", Path(tmp) / "lessons.jsonl"),
                mock.patch.object(lessons, "HANDOFF_LESSONS_PATH", Path(tmp) / "handoffs.jsonl"),
            ):
                librarian_escalate.run("t-order", "update stale doc", str(target), workdir=tmp)

            self.assertEqual(post.call_count, 3)
            call_models = [c.kwargs["json"]["model"] for c in post.call_args_list]
            call_urls = [c.args[0] for c in post.call_args_list]

            self.assertEqual(
                call_models,
                ["mistral-small:latest", "qwen2.5-coder:14b-instruct-q6_K", "stealth/ox-alpha"],
            )
            self.assertIn("localhost:11434", call_urls[0])
            self.assertIn("localhost:11434", call_urls[1])
            self.assertIn("openrouter.ai", call_urls[2])
            paid_ladder_sentinel.assert_not_called()

    # -- (6) chain exhaustion ---------------------------------------------

    def test_chain_exhaustion_writes_escalation_file_and_hands_off(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "docs" / "STALE2.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("stale doc\n", encoding="utf-8")
            logs_dir = Path(tmp) / "logs"

            responses = [_fake_response("not JSON, sorry") for _ in range(3)]

            with (
                mock.patch.object(librarian_escalate, "load_tiers", return_value=self._tier5_config()),
                mock.patch.object(librarian_escalate, "load_secrets", return_value=self._secrets()),
                mock.patch.object(llm_client.requests, "post", side_effect=responses),
                mock.patch.object(orchestrator, "ESCALATIONS_DIR", logs_dir),
                mock.patch.object(orchestrator, "ESCALATIONS_LOG", logs_dir / "escalations.jsonl"),
                mock.patch.object(lessons, "LESSONS_PATH", Path(tmp) / "lessons.jsonl"),
                mock.patch.object(lessons, "HANDOFF_LESSONS_PATH", Path(tmp) / "handoffs.jsonl"),
            ):
                result = librarian_escalate.run(
                    "t-exhausted", "update stale doc", str(target), workdir=tmp,
                )

            self.assertEqual(result["status"], "human_handoff")
            self.assertIsNone(result["resolved_by"])
            summary_path = logs_dir / "escalation_t-exhausted.md"
            self.assertTrue(summary_path.exists())
            self.assertIn("t-exhausted", summary_path.read_text(encoding="utf-8"))

    # -- (7) boundary refusal ------------------------------------------

    def test_boundary_escape_refuses_before_any_model_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp) / "project"
            workdir.mkdir()
            escaping_target = "../outside.md"

            with (
                mock.patch.object(librarian_escalate, "load_tiers", return_value=self._tier5_config()),
                mock.patch.object(librarian_escalate, "load_secrets", return_value=self._secrets()),
                mock.patch.object(librarian_escalate.llm_client, "execute_llm") as execute_llm,
            ):
                result = librarian_escalate.run(
                    "t-boundary", "escape workdir", escaping_target, workdir=str(workdir),
                )

            execute_llm.assert_not_called()
            self.assertEqual(result["status"], "error")
            self.assertIsNone(result["resolved_by"])

    # -- (8) advisory no-change verdict ----------------------------------

    def test_advisory_no_change_verdict_returns_changed_false_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "docs" / "FRESH.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            original = "# Fresh\n\nAlready up to date.\n"
            target.write_text(original, encoding="utf-8")

            with (
                mock.patch.object(librarian_escalate, "load_tiers", return_value=self._tier5_config()),
                mock.patch.object(librarian_escalate, "load_secrets", return_value=self._secrets()),
                mock.patch.object(
                    librarian_escalate.llm_client, "execute_llm",
                    return_value=('FRESH\n', "ollama", 4, 2),
                ) as execute_llm,
                mock.patch.object(librarian_escalate.content_guard, "check_write") as check_write,
                mock.patch.object(librarian_escalate, "clear_state") as clear_state,
            ):
                result = librarian_escalate.run(
                    "t-nochange", "check if guide is stale", str(target), workdir=tmp,
                )

            execute_llm.assert_called_once()
            check_write.assert_not_called()
            clear_state.assert_called_once_with("t-nochange")
            self.assertEqual(target.read_text(encoding="utf-8"), original)
            self.assertEqual(result["status"], "success")
            self.assertFalse(result["changed"])


    # -- (9) single-call-flow: FRESH verdict --------------------------------

    def test_fresh_verdict_single_call_keeps_target_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "docs" / "FRESH2.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            original = "# Fresh\n\nAlready up to date.\n"
            target.write_text(original, encoding="utf-8")

            with (
                mock.patch.object(librarian_escalate, "load_tiers", return_value=self._tier5_config()),
                mock.patch.object(librarian_escalate, "load_secrets", return_value=self._secrets()),
                mock.patch.object(
                    librarian_escalate.llm_client, "execute_llm",
                    return_value=('FRESH\n', "ollama", 4, 2),
                ) as execute_llm,
                mock.patch.object(librarian_escalate, "clear_state") as clear_state,
            ):
                result = librarian_escalate.run(
                    "t-fresh-single", "check if guide is stale", str(target), workdir=tmp,
                )

            execute_llm.assert_called_once()
            clear_state.assert_called_once_with("t-fresh-single")
            self.assertEqual(target.read_text(encoding="utf-8"), original)
            self.assertEqual(result["status"], "success")
            self.assertFalse(result["changed"])

    # -- (10) single-call-flow: SEARCH/REPLACE block ------------------------

    def test_search_replace_block_single_call_updates_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "docs" / "EDIT.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# Edit\n\nOld sentence here.\n", encoding="utf-8")

            response = (
                "<<<<<<< SEARCH\n"
                "Old sentence here.\n"
                "=======\n"
                "New sentence here.\n"
                ">>>>>>> REPLACE\n"
            )

            with (
                mock.patch.object(librarian_escalate, "load_tiers", return_value=self._tier5_config()),
                mock.patch.object(librarian_escalate, "load_secrets", return_value=self._secrets()),
                mock.patch.object(
                    librarian_escalate.llm_client, "execute_llm",
                    return_value=(response, "ollama", 12, 7),
                ) as execute_llm,
                mock.patch.object(librarian_escalate, "clear_state") as clear_state,
            ):
                result = librarian_escalate.run(
                    "t-edit-single", "keep guide fresh", str(target), workdir=tmp,
                )

            execute_llm.assert_called_once()
            clear_state.assert_called_once_with("t-edit-single")
            self.assertEqual(target.read_text(encoding="utf-8"), "# Edit\n\nNew sentence here.\n")
            self.assertEqual(result["status"], "success")
            self.assertTrue(result["changed"])

    # -- (11) single-call-flow: new file created from fenced block ----------

    def test_new_file_created_from_fenced_block_single_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "docs" / "NEW.md"
            self.assertFalse(target.exists())

            response = "```markdown\n# New Doc\n\nBrand new content.\n```"

            with (
                mock.patch.object(librarian_escalate, "load_tiers", return_value=self._tier5_config()),
                mock.patch.object(librarian_escalate, "load_secrets", return_value=self._secrets()),
                mock.patch.object(
                    librarian_escalate.llm_client, "execute_llm",
                    return_value=(response, "ollama", 6, 4),
                ) as execute_llm,
                mock.patch.object(librarian_escalate, "clear_state") as clear_state,
            ):
                result = librarian_escalate.run(
                    "t-newfile-single", "create new doc", str(target), workdir=tmp,
                )

            execute_llm.assert_called_once()
            clear_state.assert_called_once_with("t-newfile-single")
            self.assertTrue(target.exists())
            self.assertEqual(target.read_text(encoding="utf-8"), "# New Doc\n\nBrand new content.\n")
            self.assertEqual(result["status"], "success")
            self.assertTrue(result["changed"])

    # -- (12) single-call-flow: unparseable response escalates chain --------

    def test_unparseable_response_escalates_to_next_chain_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "docs" / "GARBLED.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("stale doc\n", encoding="utf-8")
            logs_dir = Path(tmp) / "logs"

            responses = [
                ("not FRESH and not a SEARCH/REPLACE block either", "ollama", 4, 2)
                for _ in range(3)
            ]

            with (
                mock.patch.object(librarian_escalate, "load_tiers", return_value=self._tier5_config()),
                mock.patch.object(librarian_escalate, "load_secrets", return_value=self._secrets()),
                mock.patch.object(
                    librarian_escalate.llm_client, "execute_llm", side_effect=responses,
                ) as execute_llm,
                mock.patch.object(orchestrator, "ESCALATIONS_DIR", logs_dir),
                mock.patch.object(orchestrator, "ESCALATIONS_LOG", logs_dir / "escalations.jsonl"),
                mock.patch.object(lessons, "LESSONS_PATH", Path(tmp) / "lessons.jsonl"),
                mock.patch.object(lessons, "HANDOFF_LESSONS_PATH", Path(tmp) / "handoffs.jsonl"),
            ):
                result = librarian_escalate.run(
                    "t-unparseable", "update stale doc", str(target), workdir=tmp,
                )

            self.assertEqual(execute_llm.call_count, 3)
            call_models = [c.kwargs["model"] for c in execute_llm.call_args_list]
            self.assertNotEqual(call_models[0], call_models[1])
            self.assertEqual(
                call_models,
                ["mistral-small:latest", "qwen2.5-coder:14b-instruct-q6_K", "stealth/ox-alpha"],
            )
            self.assertEqual(result["status"], "human_handoff")
            self.assertIsNone(result["resolved_by"])

    # -- (13) staleness pre-check ------------------------------------------

    def _init_git_repo(self, workdir: Path) -> None:
        """Create a real throwaway git repo with a scripted history."""
        import subprocess

        def git(*args: str) -> subprocess.CompletedProcess:
            return subprocess.run(
                ["git", "-C", str(workdir), *args],
                capture_output=True,
                text=True,
                check=True,
            )

        git("init")
        git("config", "user.email", "test@example.com")
        git("config", "user.name", "Test Runner")
        git("commit", "--allow-empty", "-m", "initial")

    def _commit_file(self, workdir: Path, relpath: str, content: str, message: str) -> None:
        import subprocess

        target = workdir / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(workdir), "add", relpath],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "-C", str(workdir), "commit", "-m", message],
            check=True,
            capture_output=True,
            text=True,
        )

    def test_staleness_precheck_skips_when_doc_newer_than_code(self) -> None:
        """doc newer than code + clean tree + unnamed -> execute_llm NOT called."""
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            self._init_git_repo(workdir)
            # Code committed first
            self._commit_file(workdir, "src/main.py", "print('hello')\n", "add code")
            # Doc committed after code
            self._commit_file(workdir, "docs/GUIDE.md", "# Guide\n\nFresh content.\n", "add doc")

            with (
                mock.patch.object(librarian_escalate, "load_tiers", return_value=self._tier5_config()),
                mock.patch.object(librarian_escalate, "load_secrets", return_value=self._secrets()),
                mock.patch.object(librarian_escalate.llm_client, "execute_llm") as execute_llm,
            ):
                result = librarian_escalate.run(
                    "t-stale-skip", "review documentation", str(workdir / "docs" / "GUIDE.md"),
                    workdir=str(workdir),
                )

            execute_llm.assert_not_called()
            self.assertEqual(result.get("via"), "staleness_precheck")

    def test_staleness_precheck_calls_model_when_dirty_tree(self) -> None:
        """Dirty working tree -> execute_llm called exactly once."""
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            self._init_git_repo(workdir)
            self._commit_file(workdir, "src/main.py", "print('hello')\n", "add code")
            self._commit_file(workdir, "docs/GUIDE.md", "# Guide\n\nFresh.\n", "add doc")
            # Dirty the tree
            (workdir / "src" / "main.py").write_text("print('dirty')\n", encoding="utf-8")

            with (
                mock.patch.object(librarian_escalate, "load_tiers", return_value=self._tier5_config()),
                mock.patch.object(librarian_escalate, "load_secrets", return_value=self._secrets()),
                mock.patch.object(
                    librarian_escalate.llm_client, "execute_llm",
                    return_value=('FRESH\n', "ollama", 4, 2),
                ) as execute_llm,
                mock.patch.object(librarian_escalate, "clear_state"),
            ):
                result = librarian_escalate.run(
                    "t-stale-dirty", "review documentation", str(workdir / "docs" / "GUIDE.md"),
                    workdir=str(workdir),
                )

            execute_llm.assert_called_once()

    def test_staleness_precheck_calls_model_when_code_committed_after_doc(self) -> None:
        """Code committed after the doc -> execute_llm called exactly once."""
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            self._init_git_repo(workdir)
            # Doc committed first
            self._commit_file(workdir, "docs/GUIDE.md", "# Guide\n\nFresh.\n", "add doc")
            # Code committed after doc
            self._commit_file(workdir, "src/main.py", "print('hello')\n", "add code after doc")

            with (
                mock.patch.object(librarian_escalate, "load_tiers", return_value=self._tier5_config()),
                mock.patch.object(librarian_escalate, "load_secrets", return_value=self._secrets()),
                mock.patch.object(
                    librarian_escalate.llm_client, "execute_llm",
                    return_value=('FRESH\n', "ollama", 4, 2),
                ) as execute_llm,
                mock.patch.object(librarian_escalate, "clear_state"),
            ):
                result = librarian_escalate.run(
                    "t-stale-code-after", "review documentation", str(workdir / "docs" / "GUIDE.md"),
                    workdir=str(workdir),
                )

            execute_llm.assert_called_once()

    def test_staleness_precheck_calls_model_when_doc_untracked(self) -> None:
        """Untracked doc (no commits for it) -> execute_llm called exactly once."""
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            self._init_git_repo(workdir)
            self._commit_file(workdir, "src/main.py", "print('hello')\n", "add code")
            # Doc untracked
            target = workdir / "docs" / "UNTRA.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# Untracked\n\nNew doc.\n", encoding="utf-8")

            with (
                mock.patch.object(librarian_escalate, "load_tiers", return_value=self._tier5_config()),
                mock.patch.object(librarian_escalate, "load_secrets", return_value=self._secrets()),
                mock.patch.object(
                    librarian_escalate.llm_client, "execute_llm",
                    return_value=('FRESH\n', "ollama", 4, 2),
                ) as execute_llm,
                mock.patch.object(librarian_escalate, "clear_state"),
            ):
                result = librarian_escalate.run(
                    "t-stale-untracked", "review documentation", str(target),
                    workdir=str(workdir),
                )

            execute_llm.assert_called_once()

    def test_staleness_precheck_explicit_mention_force_calls_by_relpath(self) -> None:
        """Description naming the file by relpath -> execute_llm called once."""
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            self._init_git_repo(workdir)
            self._commit_file(workdir, "doc-other.md", "# Old\n", "add doc")
            self._commit_file(workdir, "docs/GUIDE.md", "# Guide\n\nFresh.\n", "add doc fresh")
            self._commit_file(workdir, "src/main.py", "print('hello')\n", "add code")

            with (
                mock.patch.object(librarian_escalate, "load_tiers", return_value=self._tier5_config()),
                mock.patch.object(librarian_escalate, "load_secrets", return_value=self._secrets()),
                mock.patch.object(
                    librarian_escalate.llm_client, "execute_llm",
                    return_value=('FRESH\n', "ollama", 4, 2),
                ) as execute_llm,
                mock.patch.object(librarian_escalate, "clear_state"),
            ):
                result = librarian_escalate.run(
                    "t-stale-relpath", "update docs/GUIDE.md", str(workdir / "docs" / "GUIDE.md"),
                    workdir=str(workdir),
                )

            execute_llm.assert_called_once()

    def test_staleness_precheck_explicit_mention_force_calls_by_basename(self) -> None:
        """Description naming the file by basename -> execute_llm called once."""
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            self._init_git_repo(workdir)
            self._commit_file(workdir, "docs/GUIDE.md", "# Guide\n\nFresh.\n", "add doc")
            self._commit_file(workdir, "src/main.py", "print('hello')\n", "add code")

            with (
                mock.patch.object(librarian_escalate, "load_tiers", return_value=self._tier5_config()),
                mock.patch.object(librarian_escalate, "load_secrets", return_value=self._secrets()),
                mock.patch.object(
                    librarian_escalate.llm_client, "execute_llm",
                    return_value=('FRESH\n', "ollama", 4, 2),
                ) as execute_llm,
                mock.patch.object(librarian_escalate, "clear_state"),
            ):
                result = librarian_escalate.run(
                    "t-stale-basename", "update GUIDE.md", str(workdir / "docs" / "GUIDE.md"),
                    workdir=str(workdir),
                )

            execute_llm.assert_called_once()

    def test_staleness_precheck_explicit_mention_force_calls_by_stem(self) -> None:
        """Description naming the file by bare stem -> execute_llm called once."""
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            self._init_git_repo(workdir)
            self._commit_file(workdir, "docs/GUIDE.md", "# Guide\n\nFresh.\n", "add doc")
            self._commit_file(workdir, "src/main.py", "print('hello')\n", "add code")

            with (
                mock.patch.object(librarian_escalate, "load_tiers", return_value=self._tier5_config()),
                mock.patch.object(librarian_escalate, "load_secrets", return_value=self._secrets()),
                mock.patch.object(
                    librarian_escalate.llm_client, "execute_llm",
                    return_value=('FRESH\n', "ollama", 4, 2),
                ) as execute_llm,
                mock.patch.object(librarian_escalate, "clear_state"),
            ):
                result = librarian_escalate.run(
                    "t-stale-stem", "update GUIDE to be current", str(workdir / "docs" / "GUIDE.md"),
                    workdir=str(workdir),
                )

            execute_llm.assert_called_once()

    def test_staleness_precheck_fail_open_when_subprocess_raises(self) -> None:
        """Monkeypatched subprocess raising -> model still called (fail-open)."""
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            self._init_git_repo(workdir)
            self._commit_file(workdir, "docs/GUIDE.md", "# Guide\n\nFresh.\n", "add doc")
            self._commit_file(workdir, "src/main.py", "print('hello')\n", "add code")

            with (
                mock.patch.object(librarian_escalate, "load_tiers", return_value=self._tier5_config()),
                mock.patch.object(librarian_escalate, "load_secrets", return_value=self._secrets()),
                mock.patch.object(
                    librarian_escalate.llm_client, "execute_llm",
                    return_value=('FRESH\n', "ollama", 4, 2),
                ) as execute_llm,
                mock.patch.object(librarian_escalate, "clear_state"),
                mock.patch(
                    "scripts.doc_staleness.subprocess.run",
                    side_effect=RuntimeError("git exploded"),
                ),
            ):
                result = librarian_escalate.run(
                    "t-stale-failopen", "review documentation", str(workdir / "docs" / "GUIDE.md"),
                    workdir=str(workdir),
                )

            execute_llm.assert_called_once()
