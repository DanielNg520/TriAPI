import io
from unittest.mock import patch

from scripts import call_deepseek


def test_main_falls_back_to_openrouter_during_peak_hours(tmp_path, monkeypatch, capsys):
    system_file = tmp_path / "system.md"
    system_file.write_text("placeholder system prompt")

    monkeypatch.setattr("sys.argv", ["call_deepseek.py", "--system-file", str(system_file)])
    monkeypatch.setattr("sys.stdin", io.StringIO(""))

    with patch(
        "scripts.call_deepseek.llm_client.is_deepseek_peak_hours", return_value=True
    ), patch(
        "scripts.call_deepseek.llm_client.load_model_config",
        return_value={"openrouter": {"fallback_model": "nvidia/nemotron-3-ultra-550b-a55b:free"}},
    ), patch(
        "scripts.call_deepseek.cost.check_budget",
        side_effect=AssertionError("should not be called"),
    ) as check_budget, patch(
        "scripts.call_deepseek.secrets_loader.load_secrets",
        return_value={"open_router_api_key": "fake-key"},
    ), patch(
        "scripts.call_deepseek.llm_client.execute_openrouter",
        return_value=("fallback response", 10, 20),
    ) as execute_openrouter, patch(
        "scripts.call_deepseek.llm_client.execute_deepseek",
        side_effect=AssertionError("should not be called"),
    ) as execute_deepseek:
        result = call_deepseek.main()

    assert result == 0
    check_budget.assert_not_called()
    execute_deepseek.assert_not_called()
    execute_openrouter.assert_called_once()
    assert execute_openrouter.call_args.args[2] == "fake-key"
    assert "fallback response" in capsys.readouterr().out


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
        "scripts.call_deepseek.llm_client.execute_openrouter",
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

