from datetime import datetime, timezone
from unittest.mock import patch

from scripts.llm_client import execute_openrouter, extract_code_block, is_deepseek_peak_hours
from scripts.llm_client import execute_planner
from scripts.openrouter_sanitizer import _PHONE_LIKE_RE
import pytest


def test_extract_code_block_exact_language():
    response = "some text\n```python\ndef f():\n    return 1\n```\nmore text"
    assert extract_code_block(response) == "def f():\n    return 1"


def test_extract_code_block_bare_fallback():
    response = "text\n```\nkey: value\n```\n"
    assert extract_code_block(response, language="yaml") == "key: value"


def test_extract_code_block_preserves_content_whitespace():
    response = "```python\n    a = 1\n\n    b = 2   \n```"
    expected = "    a = 1\n\n    b = 2   "
    assert extract_code_block(response) == expected


def test_extract_code_block_first_block_priority():
    response = "```python\nfirst = 1\n```\n```python\nsecond = 2\n```"
    assert extract_code_block(response) == "first = 1"


def test_extract_code_block_custom_language():
    response = "text\n```yaml\nkey: value\n```\n"
    assert extract_code_block(response, language="yaml") == "key: value"


def test_extract_code_block_missing_raises_value_error():
    with pytest.raises(ValueError):
        extract_code_block("no code blocks here at all")


def test_is_deepseek_peak_hours_true_inside_window_on_weekday():
    cfg = {"deepseek": {"peak_hours_utc": [1, 4]}}
    fixed_dt = datetime(2026, 9, 8, 2, 0, tzinfo=timezone.utc)

    with patch("scripts.llm_client.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_dt
        assert is_deepseek_peak_hours(cfg) is True


def test_is_deepseek_peak_hours_false_outside_window_on_weekday():
    cfg = {"deepseek": {"peak_hours_utc": [1, 4]}}
    fixed_dt = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)

    with patch("scripts.llm_client.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_dt
        assert is_deepseek_peak_hours(cfg) is False


def test_is_deepseek_peak_hours_false_on_beijing_weekend():
    cfg = {"deepseek": {"peak_hours_utc": [1, 4]}}
    fixed_dt = datetime(2026, 9, 12, 2, 0, tzinfo=timezone.utc)

    with patch("scripts.llm_client.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_dt
        assert is_deepseek_peak_hours(cfg) is False


def test_execute_openrouter_returns_content_and_usage():
    cfg = {
        "openrouter": {
            "endpoint": "https://openrouter.ai/api/v1",
            "fallback_model": "nvidia/nemotron-3-ultra-550b-a55b:free",
        },
        "timeouts": {"http": 600},
    }
    fake_response = type(
        "Resp",
        (),
        {
            "raise_for_status": lambda self: None,
            "json": lambda self: {
                "choices": [{"message": {"content": "hello"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 7},
            },
        },
    )()

    with patch("scripts.llm_client.load_model_config", return_value=cfg), patch(
        "scripts.llm_client.requests.post", return_value=fake_response
    ) as post:
        text, in_tok, out_tok = execute_openrouter("prompt", "system", "fake-key")

    assert text == "hello"
    assert (in_tok, out_tok) == (5, 7)
    called_url = post.call_args.args[0]
    assert called_url == "https://openrouter.ai/api/v1/chat/completions"
    called_payload = post.call_args.kwargs["json"]
    assert called_payload["model"] == "nvidia/nemotron-3-ultra-550b-a55b:free"


def test_execute_openrouter_sanitizes_prompt_and_system_prompt():
    cfg = {
        "openrouter": {
            "endpoint": "https://openrouter.ai/api/v1",
            "fallback_model": "nvidia/nemotron-3-ultra-550b-a55b:free",
        },
        "timeouts": {"http": 600},
    }
    fake_response = type(
        "Resp",
        (),
        {
            "raise_for_status": lambda self: None,
            "json": lambda self: {
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        },
    )()
    phone = "555" + "-" + "555" + "-" + "5555"

    with patch("scripts.llm_client.load_model_config", return_value=cfg), patch(
        "scripts.llm_client.requests.post", return_value=fake_response
    ) as post:
        execute_openrouter(f"call {phone}", "system prompt", "fake-key")

    sent_payload = post.call_args.kwargs["json"]
    sent_prompt = sent_payload["messages"][1]["content"]
    assert phone not in sent_prompt
    assert _PHONE_LIKE_RE.search(sent_prompt) is None


def test_execute_planner_returns_content_and_usage():
    cfg = {
        "planner": {
            "endpoint": "https://openrouter.ai/api/v1",
            "model": "nvidia/nemotron-3-ultra-550b-a55b:free",
        },
        "timeouts": {"http": 600},
    }
    fake_response = type(
        "Resp",
        (),
        {
            "raise_for_status": lambda self: None,
            "json": lambda self: {
                "choices": [{"message": {"content": "hello planner"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 7},
            },
        },
    )()

    with patch("scripts.llm_client.load_model_config", return_value=cfg), patch(
        "scripts.llm_client.requests.post", return_value=fake_response
    ) as post:
        text, in_tok, out_tok = execute_planner("prompt", "system", "fake-key")

    assert text == "hello planner"
    assert (in_tok, out_tok) == (5, 7)
    called_url = post.call_args.args[0]
    assert called_url == "https://openrouter.ai/api/v1/chat/completions"
    called_payload = post.call_args.kwargs["json"]
    assert called_payload["model"] == "nvidia/nemotron-3-ultra-550b-a55b:free"


def test_execute_planner_uses_planner_config_model_not_openrouter():
    cfg = {
        "planner": {
            "endpoint": "https://openrouter.ai/api/v1",
            "model": "nvidia/nemotron-planner",
        },
        "openrouter": {
            "endpoint": "https://openrouter.ai/api/v1",
            "fallback_model": "nvidia/nemotron-openrouter-fallback",
        },
        "timeouts": {"http": 600},
    }
    fake_response = type(
        "Resp",
        (),
        {
            "raise_for_status": lambda self: None,
            "json": lambda self: {
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        },
    )()

    with patch("scripts.llm_client.load_model_config", return_value=cfg), patch(
        "scripts.llm_client.requests.post", return_value=fake_response
    ) as post:
        execute_planner("prompt", "system", "fake-key")

    called_payload = post.call_args.kwargs["json"]
    assert called_payload["model"] == "nvidia/nemotron-planner"
    assert called_payload["model"] != cfg["openrouter"]["fallback_model"]


def test_execute_planner_no_choices_raises():
    cfg = {
        "planner": {
            "endpoint": "https://openrouter.ai/api/v1",
            "model": "nvidia/nemotron-3-ultra-550b-a55b:free",
        },
        "timeouts": {"http": 600},
    }
    fake_response = type(
        "Resp",
        (),
        {
            "raise_for_status": lambda self: None,
            "json": lambda self: {
                "choices": [],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        },
    )()

    with patch("scripts.llm_client.load_model_config", return_value=cfg), patch(
        "scripts.llm_client.requests.post", return_value=fake_response
    ):
        with pytest.raises(RuntimeError):
            execute_planner("prompt", "system", "fake-key")

