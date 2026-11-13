import io
from unittest.mock import patch

from scripts import call_deepseek


def test_main_falls_back_to_agy_during_peak_hours(tmp_path, monkeypatch, capsys):
    system_file = tmp_path / "system.md"
    system_file.write_text("placeholder system prompt")

    monkeypatch.setattr("sys.argv", ["call_deepseek.py", "--system-file", str(system_file)])
    monkeypatch.setattr("sys.stdin", io.StringIO(""))

    with patch(
        "scripts.call_deepseek.llm_client.is_deepseek_peak_hours", return_value=True
    ), patch(
        "scripts.call_deepseek.llm_client.load_model_config",
        return_value={"deepseek": {"peak_fallback": {"model": "gemini-4-hydrogen-high", "effort": "high"}}},
    ), patch(
        "scripts.call_deepseek.cost.check_budget",
        side_effect=AssertionError("should not be called"),
    ) as check_budget, patch(
        "scripts.call_deepseek.secrets_loader.load_secrets",
        side_effect=AssertionError("should not be called"),
    ), patch(
        "scripts.call_deepseek.llm_client.execute_agy",
        return_value="fallback response",
    ) as execute_agy, patch(
        "scripts.call_deepseek.llm_client.execute_deepseek",
        side_effect=AssertionError("should not be called"),
    ) as execute_deepseek:
        result = call_deepseek.main()

    assert result == 0
    check_budget.assert_not_called()
    execute_deepseek.assert_not_called()
    execute_agy.assert_called_once()
    assert execute_agy.call_args.kwargs == {"model": "gemini-4-hydrogen-high", "effort": "high"}
    captured = capsys.readouterr()
    assert "fallback response" in captured.out
    assert "gemini-4-hydrogen-high" in captured.err


def test_main_blocked_during_peak_hours_with_no_fallback(tmp_path, monkeypatch, capsys):
    system_file = tmp_path / "system.md"
    system_file.write_text("placeholder system prompt")

    monkeypatch.setattr(
        "sys.argv",
        ["call_deepseek.py", "--no-fallback", "--system-file", str(system_file)],
    )
    monkeypatch.setattr("sys.stdin", io.StringIO(""))

    with patch(
        "scripts.call_deepseek.llm_client.is_deepseek_peak_hours", return_value=True
    ), patch(
        "scripts.call_deepseek.secrets_loader.load_secrets",
        side_effect=AssertionError("should not be called"),
    ), patch(
        "scripts.call_deepseek.llm_client.execute_agy",
        side_effect=AssertionError("should not be called"),
    ), patch(
        "scripts.call_deepseek.llm_client.execute_deepseek",
        side_effect=AssertionError("should not be called"),
    ), patch(
        "scripts.call_deepseek.cost.check_budget",
        side_effect=AssertionError("should not be called"),
    ):
        result = call_deepseek.main()

    assert result == 1
    captured = capsys.readouterr()
    assert "[BLOCKED]" in captured.err
    assert "fallback disabled" in captured.err


import pytest

@pytest.fixture(autouse=True)
def _no_holiday_refresh():
    with patch(
        "scripts.call_deepseek.holiday_calendar.refresh_if_stale",
        return_value=[],
    ):
        yield

def test_main_calls_refresh_if_stale_before_peak_check(tmp_path, monkeypatch, capsys):
    system_file = tmp_path / "system.md"
    system_file.write_text("placeholder system prompt")

    monkeypatch.setattr("sys.argv", ["call_deepseek.py", "--system-file", str(system_file)])
    monkeypatch.setattr("sys.stdin", io.StringIO(""))

    cfg = {"deepseek": {"peak_fallback": {"model": "gemini-4-hydrogen-high", "effort": "high"}}}
    order = []

    def refresh_side_effect(cfg_arg, today):
        order.append("refresh")
        return []

    def peak_side_effect():
        order.append("peak")
        return True

    with patch(
        "scripts.call_deepseek.holiday_calendar.refresh_if_stale",
        side_effect=refresh_side_effect,
    ) as refresh_mock, patch(
        "scripts.call_deepseek.llm_client.is_deepseek_peak_hours",
        side_effect=peak_side_effect,
    ), patch(
        "scripts.call_deepseek.llm_client.load_model_config",
        return_value=cfg,
    ), patch(
        "scripts.call_deepseek.cost.check_budget",
        side_effect=AssertionError("should not be called"),
    ) as check_budget, patch(
        "scripts.call_deepseek.secrets_loader.load_secrets",
        return_value={"open_router_api_key": "fake-key"},
    ), patch(
        "scripts.call_deepseek.llm_client.execute_agy",
        return_value="fallback response",
    ) as execute_agy, patch(
        "scripts.call_deepseek.llm_client.execute_deepseek",
        side_effect=AssertionError("should not be called"),
    ) as execute_deepseek:
        result = call_deepseek.main()

    assert order == ["refresh", "peak"]
    refresh_mock.assert_called_once()
    assert refresh_mock.call_args[0][0] is cfg

def test_main_stderr_holiday_line(tmp_path, monkeypatch, capsys):
    system_file = tmp_path / "system.md"
    system_file.write_text("placeholder system prompt")

    monkeypatch.setattr("sys.argv", ["call_deepseek.py", "--system-file", str(system_file)])
    monkeypatch.setattr("sys.stdin", io.StringIO(""))

    cfg = {"deepseek": {"peak_fallback": {"model": "gemini-4-hydrogen-high", "effort": "high"}}}

    with patch(
        "scripts.call_deepseek.holiday_calendar.refresh_if_stale",
        return_value=[2027],
    ), patch(
        "scripts.call_deepseek.llm_client.is_deepseek_peak_hours",
        return_value=True,
    ), patch(
        "scripts.call_deepseek.llm_client.load_model_config",
        return_value=cfg,
    ), patch(
        "scripts.call_deepseek.cost.check_budget",
        side_effect=AssertionError("should not be called"),
    ), patch(
        "scripts.call_deepseek.secrets_loader.load_secrets",
        return_value={"open_router_api_key": "fake-key"},
    ), patch(
        "scripts.call_deepseek.llm_client.execute_agy",
        return_value="fallback response",
    ), patch(
        "scripts.call_deepseek.llm_client.execute_deepseek",
        side_effect=AssertionError("should not be called"),
    ):
        result = call_deepseek.main()

    captured = capsys.readouterr()
    assert "[HOLIDAYS]" in captured.err
    assert "2027" in captured.err

    with patch(
        "scripts.call_deepseek.holiday_calendar.refresh_if_stale",
        return_value=[],
    ), patch(
        "scripts.call_deepseek.llm_client.is_deepseek_peak_hours",
        return_value=True,
    ), patch(
        "scripts.call_deepseek.llm_client.load_model_config",
        return_value=cfg,
    ), patch(
        "scripts.call_deepseek.cost.check_budget",
        side_effect=AssertionError("should not be called"),
    ), patch(
        "scripts.call_deepseek.secrets_loader.load_secrets",
        return_value={"open_router_api_key": "fake-key"},
    ), patch(
        "scripts.call_deepseek.llm_client.execute_agy",
        return_value="fallback response",
    ), patch(
        "scripts.call_deepseek.llm_client.execute_deepseek",
        side_effect=AssertionError("should not be called"),
    ):
        result = call_deepseek.main()

    captured = capsys.readouterr()
    assert "[HOLIDAYS]" not in captured.err

