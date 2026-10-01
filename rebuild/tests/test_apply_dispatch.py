import hashlib
from pathlib import Path

import pytest

from scripts import apply_dispatch
from scripts.dispatch import ledger_path, store_response


def write_response_text(text: str, tmp_path: Path) -> Path:
    return store_response(text)


def sha256_of(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def test_edit_success(capsys, tmp_path):
    target = tmp_path / "target.txt"
    target.write_text("a\nb\n")
    response_text = (
        "<<<<<<< SEARCH\n"
        "a\n"
        "=======\n"
        "x\n"
        ">>>>>>> REPLACE\n"
    )
    response = write_response_text(response_text, tmp_path)

    result = apply_dispatch.main(["--target", str(target), "--response", str(response)])

    assert result == 0
    assert target.read_text() == "x\nb\n"
    captured = capsys.readouterr()
    assert "PASSED" in captured.out
    assert "+1 -1" in captured.out
    ledger = ledger_path()
    lines = ledger.read_text().splitlines()
    assert lines == [sha256_of("x\nb\n")]


def test_response_outside_responses_dir_returns_2(capsys, tmp_path):
    target = tmp_path / "target.txt"
    target.write_text("unchanged\n")
    outside_response = tmp_path / "outside_response.txt"
    outside_response.write_text("not a stored response")

    result = apply_dispatch.main(["--target", str(target), "--response", str(outside_response)])

    assert result == 2
    assert target.read_text() == "unchanged\n"
    captured = capsys.readouterr()
    assert captured.out == ""


def test_search_not_present_returns_1(capsys, tmp_path):
    target = tmp_path / "target.txt"
    target.write_text("a\nb\n")
    response_text = (
        "<<<<<<< SEARCH\n"
        "not there\n"
        "=======\n"
        "x\n"
        ">>>>>>> REPLACE\n"
    )
    response = write_response_text(response_text, tmp_path)

    result = apply_dispatch.main(["--target", str(target), "--response", str(response)])

    assert result == 1
    assert target.read_text() == "a\nb\n"
    captured = capsys.readouterr()
    assert captured.err != ""
    assert captured.out == ""
    if ledger_path().exists():
        assert ledger_path().read_text() == ""


def test_new_success(capsys, tmp_path):
    target = tmp_path / "new_file.py"
    fenced_body = "def hello():\n    return 1"
    response_text = f"```python\n{fenced_body}\n```\n"
    response = write_response_text(response_text, tmp_path)

    result = apply_dispatch.main(
        ["--target", str(target), "--response", str(response), "--new"]
    )

    assert result == 0
    assert target.read_text() == fenced_body + "\n"
    captured = capsys.readouterr()
    assert "PASSED" in captured.out
    ledger = ledger_path()
    assert ledger.read_text().splitlines() == [sha256_of(fenced_body + "\n")]


def test_new_target_exists_returns_1(capsys, tmp_path):
    target = tmp_path / "existing.txt"
    target.write_text("original\n")
    response_text = "```python\nnew content\n```\n"
    response = write_response_text(response_text, tmp_path)

    result = apply_dispatch.main(
        ["--target", str(target), "--response", str(response), "--new"]
    )

    assert result == 1
    assert target.read_text() == "original\n"
    captured = capsys.readouterr()
    assert captured.err != ""
    assert captured.out == ""


def test_new_no_fenced_block_returns_1(capsys, tmp_path):
    target = tmp_path / "no_block.txt"
    response_text = "no fenced code here"
    response = write_response_text(response_text, tmp_path)

    result = apply_dispatch.main(
        ["--target", str(target), "--response", str(response), "--new"]
    )

    assert result == 1
    assert not target.exists()
    captured = capsys.readouterr()
    assert captured.err != ""
    assert captured.out == ""


def test_new_verify_failure_rolled_back(capsys, monkeypatch, tmp_path):
    target = tmp_path / "rolled_back.txt"
    fenced_body = "temporary"
    response_text = f"```python\n{fenced_body}\n```\n"
    response = write_response_text(response_text, tmp_path)

    monkeypatch.setattr(
        "scripts.apply_dispatch.dispatch_task",
        lambda *a, **k: {
            "passed": False,
            "summary": "bad",
            "evidence": {},
            "rolled_back": True,
        },
    )

    result = apply_dispatch.main(
        ["--target", str(target), "--response", str(response), "--new"]
    )

    assert result == 1
    assert not target.exists()
    captured = capsys.readouterr()
    assert "FAILED (rolled back)" in captured.out
