from pathlib import Path

from scripts import call_agy


def test_main_stores_response_and_prints_path(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(call_agy.llm_client, "load_rules", lambda: "RULES")
    monkeypatch.setattr(call_agy.llm_client, "execute_agy", lambda prompt, system: "agy reply")

    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("do a thing")
    monkeypatch.setattr("sys.argv", ["call_agy.py", "--prompt-file", str(prompt_file)])

    result = call_agy.main()

    captured = capsys.readouterr()
    assert result == 0
    assert "agy reply" in captured.out
    stderr_lines = captured.err.splitlines()
    response_lines = [line for line in stderr_lines if line.startswith("[response] ")]
    assert len(response_lines) == 1
    response_path_str = response_lines[0][len("[response] "):]
    response_path = Path(response_path_str)
    assert response_path.exists()
    assert response_path.parent == tmp_path / "responses"
    assert response_path.read_text() == "agy reply"
