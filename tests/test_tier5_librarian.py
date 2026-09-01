"""Regression tests for the Tier 5 (librarian) doc-fix pipeline.

Split out of test_branch_features.py (2026-08-24): that file was already at
the 73728-char Tier 4 context ceiling (content_guard.check_write's
MAX_WRITE_CHARS), so appending a whole new TestTier5Librarian class there
would have authored a file Tier 4 could never edit again. See
scripts/content_guard.py's own docstring for why that's a one-way door.

Every test here patches strictly at the HTTP boundary (llm_client.requests)
or at the module-function boundary already used elsewhere in this suite
(mirrors LlmClientOpenAIErrorBodyTests / the tier1/2 escalate tests in
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
        # No fallback chain (removed 2026-09-01): a single `primary` model
        # slot, `agy` provider always -- any failure escalates straight to
        # human_handoff, no fallback_local/fallback_agy/fallback_openrouter
        # legs to try. `threshold` still gates the verify-failure retry
        # count enforced across external dispatcher retries (see
        # librarian_escalate.run's docstring), not a chain traversal.
        return {
            "tier_5_librarian": {
                "enabled": True,
                "role": "doc_librarian",
                "provider": "agy",
                "effort": "high",
                "models": {
                    "primary": "mistral-small:latest",
                },
                "target_globs": ["*.md", "docs/**"],
                "verify_command": None,
                "max_attempts": 2,
            },
            "escalation_rules": {
                "tier5_to_fallbacks": {
                    "threshold": 2,
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

    def test_primary_provider_swaps_to_agy_with_effort_when_configured(self) -> None:
        """Primary provider configured as agy uses execute_agy and never
        touches the paid ladder or the local/openrouter fallbacks."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "docs" / "GUIDE.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# Guide\n\nOld sentence here.\n", encoding="utf-8")

            config = self._tier5_config()
            config["tier_5_librarian"]["provider"] = "agy"
            config["tier_5_librarian"]["effort"] = "low"
            config["tier_5_librarian"]["models"]["primary"] = "gemini-3.7-flash"

            response = (
                "<<<<<<< SEARCH\n"
                "Old sentence here.\n"
                "=======\n"
                "New sentence here.\n"
                ">>>>>>> REPLACE\n"
            )
            agy_sentinel = mock.Mock(return_value=(response, "subscription", 12, 7))

            with (
                mock.patch.object(librarian_escalate, "load_tiers", return_value=config),
                mock.patch.object(librarian_escalate, "load_secrets", return_value=self._secrets()),
                mock.patch.object(librarian_escalate.llm_client, "execute_agy", new=agy_sentinel),
                mock.patch.object(librarian_escalate.llm_client, "execute_llm") as execute_llm,
                mock.patch.object(llm_client, "_call_claude_cli") as claude_cli,
                mock.patch.object(llm_client, "_call_gemini_api") as gemini_api,
                mock.patch.object(tier1_escalate, "escalate") as tier1_escalate_mock,
                mock.patch.object(tier2_escalate, "escalate") as tier2_escalate_mock,
                mock.patch.object(librarian_escalate, "clear_state") as clear_state,
            ):
                result = librarian_escalate.run(
                    "t-agy-primary", "keep guide fresh", str(target), workdir=tmp,
                )

            # Primary path used execute_agy exactly once, with the
            # configured model/effort -- proves the new primary provider
            # slot is wired through, not silently falling back to ollama.
            agy_sentinel.assert_called_once()
            self.assertEqual(agy_sentinel.call_args.kwargs["model"], "gemini-3.7-flash")
            self.assertEqual(agy_sentinel.call_args.kwargs["effort"], "low")

            # fallback_local (ollama/openrouter path) is never reached
            # because primary succeeded on the first attempt.
            execute_llm.assert_not_called()

            # The paid ladder (Claude CLI, Gemini API, Tier 1/2 escalate)
            # must never be touched by the librarian tier at all.
            claude_cli.assert_not_called()
            gemini_api.assert_not_called()
            tier1_escalate_mock.assert_not_called()
            tier2_escalate_mock.assert_not_called()

            clear_state.assert_called_once_with("t-agy-primary")
            self.assertEqual(target.read_text(encoding="utf-8"), "# Guide\n\nNew sentence here.\n")
            self.assertEqual(result["status"], "success")
            self.assertTrue(result["changed"])

    # -- (6) chain exhaustion ---------------------------------------------

    def test_chain_exhaustion_writes_escalation_file_and_hands_off(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "docs" / "STALE2.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("stale doc\n", encoding="utf-8")
            logs_dir = Path(tmp) / "logs"

            responses = [_fake_response("not JSON, sorry") for _ in range(3)]
            agy_sentinel = mock.Mock(
                return_value=("not JSON, sorry", "subscription", 4, 2)
            )

            with (
                mock.patch.object(librarian_escalate, "load_tiers", return_value=self._tier5_config()),
                mock.patch.object(librarian_escalate, "load_secrets", return_value=self._secrets()),
                mock.patch.object(llm_client.requests, "post", side_effect=responses),
                mock.patch.object(librarian_escalate.llm_client, "execute_agy", new=agy_sentinel),
                mock.patch.object(orchestrator, "ESCALATIONS_DIR", logs_dir),
                mock.patch.object(orchestrator, "ESCALATIONS_LOG", logs_dir / "escalations.jsonl"),
                mock.patch.object(lessons, "LESSONS_PATH", Path(tmp) / "lessons.jsonl"),
                mock.patch.object(lessons, "HANDOFF_LESSONS_PATH", Path(tmp) / "handoffs.jsonl"),
                mock.patch.object(
                    orchestrator, "human_handoff", wraps=orchestrator.human_handoff,
                ) as human_handoff,
            ):
                result = librarian_escalate.run(
                    "t-exhausted", "update stale doc", str(target), workdir=tmp,
                )

            agy_sentinel.assert_called_once()
            human_handoff.assert_called_once()
            handoff_reason = human_handoff.call_args.args[1]
            self.assertNotIn("primary -> fallback_local -> fallback_agy -> fallback_openrouter", handoff_reason)
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
                    librarian_escalate.llm_client, "execute_agy",
                    return_value=('FRESH\n', "subscription", 4, 2),
                ) as execute_agy,
                mock.patch.object(librarian_escalate.content_guard, "check_write") as check_write,
                mock.patch.object(librarian_escalate, "clear_state") as clear_state,
            ):
                result = librarian_escalate.run(
                    "t-nochange", "check if guide is stale", str(target), workdir=tmp,
                )

            execute_agy.assert_called_once()
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
                    librarian_escalate.llm_client, "execute_agy",
                    return_value=('FRESH\n', "subscription", 4, 2),
                ) as execute_agy,
                mock.patch.object(librarian_escalate, "clear_state") as clear_state,
            ):
                result = librarian_escalate.run(
                    "t-fresh-single", "check if guide is stale", str(target), workdir=tmp,
                )

            execute_agy.assert_called_once()
            clear_state.assert_called_once_with("t-fresh-single")
            self.assertEqual(target.read_text(encoding="utf-8"), original)
            self.assertEqual(result["status"], "success")
            self.assertFalse(result["changed"])

    # -- (9b) FRESH claim contradicted by verify_cmd is rejected, not trusted --

    def test_fresh_verdict_rejected_when_verify_cmd_contradicts_it(self) -> None:
        # Recurring bug (4+ confirmed live instances): the model claims FRESH
        # even though the file still needs the described edit. A caller who
        # supplies a real (non-trivial) verify_cmd must have that claim
        # checked against the file on disk, not trusted unconditionally --
        # the primary model's FRESH claim is contradicted by verify_cmd
        # ("false"), and with no fallback chain the run must go straight to
        # human_handoff on this single attempt rather than falsely reporting
        # success.
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "docs" / "STILL_STALE.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            original = "# Doc\n\nversion 1.0.0\n"
            target.write_text(original, encoding="utf-8")

            agy_sentinel = mock.Mock(return_value=('FRESH\n', "subscription", 4, 2))

            with (
                mock.patch.object(librarian_escalate, "load_tiers", return_value=self._tier5_config()),
                mock.patch.object(librarian_escalate, "load_secrets", return_value=self._secrets()),
                mock.patch.object(librarian_escalate.llm_client, "execute_agy", new=agy_sentinel),
                mock.patch.object(librarian_escalate, "_escalate_to_human") as escalate_to_human,
                mock.patch.object(librarian_escalate, "clear_state") as clear_state,
            ):
                result = librarian_escalate.run(
                    "t-fresh-rejected", "update the version number to 2.0.0", str(target),
                    workdir=tmp, verify_cmd="false",
                )

            agy_sentinel.assert_called_once()
            clear_state.assert_not_called()
            escalate_to_human.assert_called_once()
            self.assertEqual(target.read_text(encoding="utf-8"), original)
            self.assertEqual(result["status"], "human_handoff")
            self.assertIsNone(result["resolved_by"])

    def test_fresh_verdict_trusted_when_verify_cmd_confirms_it(self) -> None:
        # Same shape as the rejection test above, but verify_cmd ("true")
        # doesn't contradict the claim -- FRESH must still be trusted and
        # return success on the very first (primary) attempt, same as the
        # no-verify_cmd case.
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "docs" / "ACTUALLY_FRESH.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            original = "# Doc\n\nversion 2.0.0\n"
            target.write_text(original, encoding="utf-8")

            with (
                mock.patch.object(librarian_escalate, "load_tiers", return_value=self._tier5_config()),
                mock.patch.object(librarian_escalate, "load_secrets", return_value=self._secrets()),
                mock.patch.object(
                    librarian_escalate.llm_client, "execute_agy",
                    return_value=('FRESH\n', "subscription", 4, 2),
                ) as execute_agy,
                mock.patch.object(librarian_escalate, "clear_state") as clear_state,
            ):
                result = librarian_escalate.run(
                    "t-fresh-confirmed", "update the version number to 2.0.0", str(target),
                    workdir=tmp, verify_cmd="true",
                )

            execute_agy.assert_called_once()
            clear_state.assert_called_once_with("t-fresh-confirmed")
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
                    librarian_escalate.llm_client, "execute_agy",
                    return_value=(response, "subscription", 12, 7),
                ) as execute_agy,
                mock.patch.object(librarian_escalate, "clear_state") as clear_state,
            ):
                result = librarian_escalate.run(
                    "t-edit-single", "keep guide fresh", str(target), workdir=tmp,
                )

            execute_agy.assert_called_once()
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
                    librarian_escalate.llm_client, "execute_agy",
                    return_value=(response, "subscription", 6, 4),
                ) as execute_agy,
                mock.patch.object(librarian_escalate, "clear_state") as clear_state,
            ):
                result = librarian_escalate.run(
                    "t-newfile-single", "create new doc", str(target), workdir=tmp,
                )

            execute_agy.assert_called_once()
            clear_state.assert_called_once_with("t-newfile-single")
            self.assertTrue(target.exists())
            self.assertEqual(target.read_text(encoding="utf-8"), "# New Doc\n\nBrand new content.\n")
            self.assertEqual(result["status"], "success")
            self.assertTrue(result["changed"])

    # -- (12) single-call-flow: unparseable response escalates chain --------

    def test_unparseable_response_escalates_to_human_handoff(self) -> None:
        # No fallback chain (removed 2026-09-01): an unparseable primary
        # response escalates straight to human_handoff on this one attempt,
        # it never tries a second/third model.
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "docs" / "GARBLED.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("stale doc\n", encoding="utf-8")
            logs_dir = Path(tmp) / "logs"

            agy_sentinel = mock.Mock(
                return_value=("not FRESH and not a SEARCH/REPLACE block either", "subscription", 4, 2)
            )

            with (
                mock.patch.object(librarian_escalate, "load_tiers", return_value=self._tier5_config()),
                mock.patch.object(librarian_escalate, "load_secrets", return_value=self._secrets()),
                mock.patch.object(librarian_escalate.llm_client, "execute_agy", new=agy_sentinel),
                mock.patch.object(orchestrator, "ESCALATIONS_DIR", logs_dir),
                mock.patch.object(orchestrator, "ESCALATIONS_LOG", logs_dir / "escalations.jsonl"),
                mock.patch.object(lessons, "LESSONS_PATH", Path(tmp) / "lessons.jsonl"),
                mock.patch.object(lessons, "HANDOFF_LESSONS_PATH", Path(tmp) / "handoffs.jsonl"),
            ):
                result = librarian_escalate.run(
                    "t-unparseable", "update stale doc", str(target), workdir=tmp,
                )

            agy_sentinel.assert_called_once()
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
                    "t-stale-skip", "is the documentation stale relative to the code", str(workdir / "docs" / "GUIDE.md"),
                    workdir=str(workdir),
                )

            execute_llm.assert_not_called()
            self.assertEqual(result.get("via"), "staleness_precheck")

    def test_staleness_precheck_skips_only_with_staleness_phrase_and_genuinely_fresh_doc(self) -> None:
        """doc newer than code + clean tree + staleness phrase -> execute_llm NOT called."""
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
                    "t-precheck-staleness-phrase-fresh-doc", 
                    "is this doc out of date", 
                    str(workdir / "docs" / "GUIDE.md"),
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
                    librarian_escalate.llm_client, "execute_agy",
                    return_value=('FRESH\n', "subscription", 4, 2),
                ) as execute_agy,
                mock.patch.object(librarian_escalate, "clear_state"),
            ):
                result = librarian_escalate.run(
                    "t-stale-dirty", "is the documentation up to date", str(workdir / "docs" / "GUIDE.md"),
                    workdir=str(workdir),
                )

            execute_agy.assert_called_once()

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
                    librarian_escalate.llm_client, "execute_agy",
                    return_value=('FRESH\n', "subscription", 4, 2),
                ) as execute_agy,
                mock.patch.object(librarian_escalate, "clear_state"),
            ):
                result = librarian_escalate.run(
                    "t-stale-code-after", "is the documentation up to date with the code", str(workdir / "docs" / "GUIDE.md"),
                    workdir=str(workdir),
                )

            execute_agy.assert_called_once()

    def test_staleness_precheck_forces_call_for_non_staleness_description_even_when_fresh(self) -> None:
        """Non-staleness description + doc newer than code + clean tree -> execute_llm called once."""
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
                mock.patch.object(
                    librarian_escalate.llm_client, "execute_agy",
                    return_value=('FRESH\n', "subscription", 4, 2),
                ) as execute_agy,
            ):
                result = librarian_escalate.run(
                    "t-non-staleness", "append a note recording that X changed", str(workdir / "docs" / "GUIDE.md"),
                    workdir=str(workdir),
                )

            execute_agy.assert_called_once()

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
                    librarian_escalate.llm_client, "execute_agy",
                    return_value=('FRESH\n', "subscription", 4, 2),
                ) as execute_agy,
                mock.patch.object(librarian_escalate, "clear_state"),
            ):
                result = librarian_escalate.run(
                    "t-stale-untracked", "is the documentation out of date", str(target),
                    workdir=str(workdir),
                )

            execute_agy.assert_called_once()

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
                    librarian_escalate.llm_client, "execute_agy",
                    return_value=('FRESH\n', "subscription", 4, 2),
                ) as execute_agy,
                mock.patch.object(librarian_escalate, "clear_state"),
            ):
                result = librarian_escalate.run(
                    "t-stale-relpath", "is docs/GUIDE.md stale or out of date", str(workdir / "docs" / "GUIDE.md"),
                    workdir=str(workdir),
                )

            execute_agy.assert_called_once()

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
                    librarian_escalate.llm_client, "execute_agy",
                    return_value=('FRESH\n', "subscription", 4, 2),
                ) as execute_agy,
                mock.patch.object(librarian_escalate, "clear_state"),
            ):
                result = librarian_escalate.run(
                    "t-stale-basename", "is GUIDE.md up to date", str(workdir / "docs" / "GUIDE.md"),
                    workdir=str(workdir),
                )

            execute_agy.assert_called_once()

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
                    librarian_escalate.llm_client, "execute_agy",
                    return_value=('FRESH\n', "subscription", 4, 2),
                ) as execute_agy,
                mock.patch.object(librarian_escalate, "clear_state"),
            ):
                result = librarian_escalate.run(
                    "t-stale-stem", "is GUIDE stale", str(workdir / "docs" / "GUIDE.md"),
                    workdir=str(workdir),
                )

            execute_agy.assert_called_once()

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
                    librarian_escalate.llm_client, "execute_agy",
                    return_value=('FRESH\n', "subscription", 4, 2),
                ) as execute_agy,
                mock.patch.object(librarian_escalate, "clear_state"),
                mock.patch(
                    "scripts.doc_staleness.subprocess.run",
                    side_effect=RuntimeError("git exploded"),
                ),
            ):
                result = librarian_escalate.run(
                    "t-stale-failopen", "is the documentation up to date with the code", str(workdir / "docs" / "GUIDE.md"),
                    workdir=str(workdir),
                )

            execute_agy.assert_called_once()

    def test_should_skip_model_call_returns_false_immediately_for_non_staleness_description(self) -> None:
        from scripts import doc_staleness
        with tempfile.TemporaryDirectory() as tmp:
            doc_path = Path(tmp) / "dummy.md"
            result = doc_staleness.should_skip_model_call(
                str(doc_path), tmp, "append this note to the index"
            )
            self.assertEqual(
                result,
                (False, "task description is not a code-sync staleness check -- skipping the fast-path, forcing a real edit attempt")
            )
