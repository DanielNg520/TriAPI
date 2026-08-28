import subprocess
from unittest import TestCase, mock

from scripts import llm_client


class TestLLMClientAgyArgvGuard(TestCase):
    """Regression coverage for the agy 'Argument list too long' crash fix
    (2026-08-28): a prompt too large for argv must raise a controlled
    subprocess.CalledProcessError before subprocess.run() is ever invoked,
    not an uncaught OSError (E2BIG) from the OS itself."""

    @mock.patch('scripts.llm_client.subprocess.run')
    def test_oversized_prompt_raises_before_subprocess_run(self, mock_run):
        oversized_prompt = 'x' * (llm_client._AGY_MAX_PROMPT_CHARS + 1)
        with self.assertRaises(subprocess.CalledProcessError):
            llm_client._call_agy_cli(oversized_prompt, model='gemini-3.1-pro', effort='high')
        mock_run.assert_not_called()

    @mock.patch('scripts.llm_client.subprocess.run')
    def test_oversized_combined_prompt_and_system_prompt_raises(self, mock_run):
        # system_prompt is prepended to prompt before the size check, so the
        # combined length -- not just prompt alone -- must trip the guard.
        prompt = 'x' * (llm_client._AGY_MAX_PROMPT_CHARS - 10)
        system_prompt = 'y' * 100
        with self.assertRaises(subprocess.CalledProcessError):
            llm_client._call_agy_cli(prompt, model='gemini-3.1-pro', effort='high', system_prompt=system_prompt)
        mock_run.assert_not_called()

    @mock.patch('scripts.llm_client.subprocess.run')
    def test_normal_sized_prompt_still_calls_subprocess_run(self, mock_run):
        mock_result = mock.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"status": "SUCCESS", "response": "ok"}'
        mock_run.return_value = mock_result

        response, billing, in_tok, out_tok = llm_client._call_agy_cli(
            'a short prompt', model='gemini-3.1-pro', effort='high'
        )

        mock_run.assert_called_once()
        self.assertEqual(response, 'ok')
        self.assertEqual(billing, 'agy')
