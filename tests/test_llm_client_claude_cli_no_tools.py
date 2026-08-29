from unittest import TestCase, mock

from scripts import llm_client


class TestClaudeCliDisablesTools(TestCase):
    """Regression coverage for the Tier 1 direct-mutation bug (2026-08-29):
    _call_claude_cli() must always pass `--tools ""`, forcing `claude -p`
    into a pure text-in/text-out completion backend -- the same contract
    Tier 2/3's plain HTTP calls have. Found live: without this flag, Tier 1
    is a fully agentic CLI that inherits the caller's cwd (the real target
    repo) and can Read/Edit/Bash it directly, invisible to edit_blocks.py's
    SEARCH/REPLACE parsing and every downstream safety check (content_guard,
    scope_guard, mock_patch_lint) -- a real edit landed on disk while the
    pipeline reported total failure (no parseable blocks) and escalated to
    human_handoff."""

    @mock.patch("scripts.llm_client.subprocess.run")
    def test_tools_disabled_with_model_and_effort(self, mock_run):
        mock_result = mock.MagicMock()
        mock_result.stdout = "some response"
        mock_run.return_value = mock_result

        llm_client._call_claude_cli(
            "a prompt", "a system prompt", model="claude-sonnet-5", effort="high"
        )

        mock_run.assert_called_once()
        cmd = mock_run.call_args.args[0]
        self.assertIn("--tools", cmd)
        idx = cmd.index("--tools")
        self.assertEqual(cmd[idx + 1], "")

    @mock.patch("scripts.llm_client.subprocess.run")
    def test_tools_disabled_with_no_model_or_effort(self, mock_run):
        mock_result = mock.MagicMock()
        mock_result.stdout = "some response"
        mock_run.return_value = mock_result

        llm_client._call_claude_cli("a prompt", "a system prompt")

        cmd = mock_run.call_args.args[0]
        idx = cmd.index("--tools")
        self.assertEqual(cmd[idx + 1], "")
