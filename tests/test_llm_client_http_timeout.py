import os
from unittest import TestCase, mock
import importlib
from scripts import llm_client

class TestLLMClientHTTPTimeout(TestCase):
    def test_default_timeout(self):
        self.assertEqual(llm_client._HTTP_TIMEOUT, 600)

    @mock.patch('os.getenv', return_value='900')
    def test_env_override_timeout(self, mock_getenv):
        importlib.reload(llm_client)
        self.assertEqual(llm_client._HTTP_TIMEOUT, 900)

    @mock.patch('os.getenv', return_value='invalid')
    def test_env_override_invalid_timeout(self, mock_getenv):
        importlib.reload(llm_client)
        self.assertEqual(llm_client._HTTP_TIMEOUT, 600)

    def tearDown(self):
        os.environ.pop('TRIAPI_HTTP_TIMEOUT', None)
        importlib.reload(llm_client)

    @mock.patch('scripts.llm_client.requests.post')
    def test_timeout_in_call_openai_api(self, mock_post):
        mock_response = mock.MagicMock()
        # The response payload includes 'choices' and 'usage' because _call_openai_api
        # unpacks them; without these, the function would crash before returning, failing the test.
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'response'}}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 20}
        }
        mock_post.return_value = mock_response
        llm_client._call_openai_api('endpoint', 'key', 'model', 'prompt', 'system_prompt', provider='openai')
        
        # Hardcoding the expected URL to verify correct endpoint construction rather than 
        # dynamically rebuilding it, ensuring any path logic changes in the implementation are caught.
        mock_post.assert_called_once_with(
            'endpoint/chat/completions',
            headers={'Authorization': 'Bearer key', 'Content-Type': 'application/json'},
            json={'model': 'model', 'messages': [{'role': 'system', 'content': 'system_prompt'}, {'role': 'user', 'content': 'prompt'}]},
            timeout=llm_client._HTTP_TIMEOUT
        )

    @mock.patch('scripts.llm_client.requests.post')
    def test_timeout_in_call_gemini_api(self, mock_post):
        mock_response = mock.MagicMock()
        # Required response payload structure for _call_gemini_api to extract the text successfully.
        mock_response.json.return_value = {'candidates': [{'content': {'parts': [{'text': 'response'}]}}]}
        mock_post.return_value = mock_response
        
        # Verifies that Gemini routing respects the passed-in endpoint rather than
        # falling back to a hardcoded DEFAULT_GOOGLE_API_ROOT.
        llm_client._call_gemini_api('endpoint', 'key', 'model', 'prompt', 'system_prompt')
        
        # Hardcoding the expected URL to verify correct endpoint construction independently.
        mock_post.assert_called_once_with(
            "endpoint/v1beta/models/model:generateContent?key=key",
            json={
                "contents": [{"parts": [{"text": "prompt"}]}],
                "system_instruction": {"parts": [{"text": "system_prompt"}]},
            },
            timeout=llm_client._HTTP_TIMEOUT
        )
