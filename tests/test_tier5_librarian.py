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
                "```json\n"
                "{\n"
                '  "stale": true,\n'
                '  "updated_content": "<<<<<<< SEARCH\\nOld sentence here.\\n'
                '=======\\nNew sentence here.\\n>>>>>>> REPLACE"\n'
                "}\n```"
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
                    return_value=('{"stale": false}', "ollama", 4, 2),
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


if __name__ == "__main__":
    unittest.main()
