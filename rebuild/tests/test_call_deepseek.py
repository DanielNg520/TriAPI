import io
from unittest.mock import patch

from scripts import call_deepseek


def test_main_returns_1_and_skips_call_during_peak_hours(tmp_path, monkeypatch):
    system_file = tmp_path / "system.md"
    system_file.write_text("placeholder system prompt")

    monkeypatch.setattr("sys.argv", ["call_deepseek.py", "--system-file", str(system_file)])
    monkeypatch.setattr("sys.stdin", io.StringIO(""))

    with patch(
        "scripts.call_deepseek.llm_client.is_deepseek_peak_hours", return_value=True
    ), patch(
        "scripts.call_deepseek.cost.check_budget",
        side_effect=AssertionError("should not be called"),
    ) as check_budget, patch(
        "scripts.call_deepseek.secrets_loader.load_secrets",
        side_effect=AssertionError("should not be called"),
    ) as load_secrets:
        result = call_deepseek.main()

    assert result == 1
    check_budget.assert_not_called()
    load_secrets.assert_not_called()
