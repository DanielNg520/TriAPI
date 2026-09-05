import pytest
from unittest.mock import patch

from scripts.dispatch import apply_change, restore_file, dispatch_task


def test_apply_change_new_content(tmp_path):
    path = tmp_path / "file.txt"
    path.write_text("old\n")

    original = apply_change(path, new_content="new\n")

    assert original == "old\n"
    assert path.read_text() == "new\n"


def test_apply_change_search_replace_blocks(tmp_path):
    path = tmp_path / "file.txt"
    path.write_text("aaa bbb ccc\n")

    apply_change(path, search_replace_blocks=[("aaa", "xxx"), ("ccc", "zzz")])

    assert path.read_text() == "xxx bbb zzz\n"


def test_apply_change_missing_or_duplicate_search_blocks(tmp_path):
    duplicate_path = tmp_path / "duplicate.txt"
    duplicate_path.write_text("aaa bbb aaa\n")
    original_duplicate = duplicate_path.read_text()

    with pytest.raises(ValueError):
        apply_change(duplicate_path, search_replace_blocks=[("aaa", "x")])
    assert duplicate_path.read_text() == original_duplicate

    missing_path = tmp_path / "missing.txt"
    missing_path.write_text("bbb\n")
    original_missing = missing_path.read_text()

    with pytest.raises(ValueError):
        apply_change(missing_path, search_replace_blocks=[("aaa", "x")])
    assert missing_path.read_text() == original_missing


def test_restore_file(tmp_path):
    path = tmp_path / "file.txt"
    path.write_text("modified\n")

    restore_file(path, "original\n")

    assert path.read_text() == "original\n"


def test_dispatch_task_success(tmp_path):
    path = tmp_path / "file.txt"
    path.write_text("old\n")

    with patch("scripts.dispatch.verify_task") as mock_verify:
        mock_verify.return_value = {"passed": True, "summary": "ok", "evidence": {}}
        result = dispatch_task(path, new_content="new\n")

    assert result["passed"] is True
    assert result["rolled_back"] is False
    assert path.read_text() == "new\n"


def test_dispatch_task_verification_failure_triggers_rollback(tmp_path):
    path = tmp_path / "file.txt"
    path.write_text("old\n")

    with patch("scripts.dispatch.verify_task") as mock_verify:
        mock_verify.return_value = {"passed": False, "summary": "bad", "evidence": {}}
        result = dispatch_task(path, new_content="new\n")

    assert result["passed"] is False
    assert result["rolled_back"] is True
    assert path.read_text() == "old\n"


def test_dispatch_task_apply_error_returns_failure(tmp_path):
    path = tmp_path / "file.txt"
    path.write_text("aaa aaa\n")
    original = path.read_text()

    with patch("scripts.dispatch.verify_task") as mock_verify:
        result = dispatch_task(path, search_replace_blocks=[("aaa", "x")])

    assert result["passed"] is False
    assert result["rolled_back"] is False
    assert "Dispatch error" in result["summary"]
    assert path.read_text() == original
    mock_verify.assert_not_called()