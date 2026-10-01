import hashlib

from scripts.dispatch import dispatch_task, ledger_path, record_applied


def test_ledger_path_honors_env_var(isolated_ledger, monkeypatch):
    custom = isolated_ledger.parent / "custom" / "ledger.sha256"
    monkeypatch.setenv("DISPATCH_LEDGER_PATH", str(custom))
    assert ledger_path() == custom


def test_ledger_path_default_when_env_missing(monkeypatch):
    monkeypatch.delenv("DISPATCH_LEDGER_PATH", raising=False)
    path = ledger_path()
    assert str(path).endswith(".local/state/dispatch-ledger/applied.sha256")


def test_record_applied_appends_correct_sha256(tmp_path, monkeypatch):
    ledger = tmp_path / "nested" / "dir" / "applied.sha256"
    monkeypatch.setenv("DISPATCH_LEDGER_PATH", str(ledger))
    file = tmp_path / "file.txt"
    file.write_text("hello world")

    record_applied(str(file))

    expected = hashlib.sha256(b"hello world").hexdigest() + "\n"
    assert ledger.read_text() == expected
    assert ledger.parent.exists()


def test_record_applied_two_calls_append_two_lines(tmp_path, monkeypatch):
    ledger = tmp_path / "applied.sha256"
    monkeypatch.setenv("DISPATCH_LEDGER_PATH", str(ledger))
    file1 = tmp_path / "f1.txt"
    file2 = tmp_path / "f2.txt"
    file1.write_text("first")
    file2.write_text("second")

    record_applied(str(file1))
    record_applied(str(file2))

    lines = ledger.read_text().strip().splitlines()
    assert lines == [
        hashlib.sha256(b"first").hexdigest(),
        hashlib.sha256(b"second").hexdigest(),
    ]


def test_dispatch_task_success_records_final_content_hash(
    tmp_path, isolated_ledger, monkeypatch
):
    from scripts import dispatch as dispatch_module

    file = tmp_path / "task.txt"
    file.write_text("original\n")
    new_content = "final content\n"

    monkeypatch.setattr(
        dispatch_module,
        "verify_task",
        lambda **kwargs: {"passed": True, "summary": "ok", "evidence": {}},
    )

    dispatch_task(str(file), new_content=new_content)

    expected = hashlib.sha256(new_content.encode()).hexdigest() + "\n"
    assert isolated_ledger.read_text() == expected


def test_dispatch_task_verify_failure_rolls_back_and_no_ledger(
    tmp_path, isolated_ledger, monkeypatch
):
    from scripts import dispatch as dispatch_module

    file = tmp_path / "task.txt"
    original = "original\n"
    file.write_text(original)

    monkeypatch.setattr(
        dispatch_module,
        "verify_task",
        lambda **kwargs: {"passed": False, "summary": "bad", "evidence": {}},
    )

    dispatch_task(str(file), new_content="changed\n")

    assert file.read_text() == original
    assert not isolated_ledger.exists()


def test_dispatch_task_apply_error_no_ledger(tmp_path, isolated_ledger, monkeypatch):
    from scripts import dispatch as dispatch_module

    file = tmp_path / "task.txt"
    content = "aaa aaa\n"
    file.write_text(content)

    monkeypatch.setattr(
        dispatch_module,
        "verify_task",
        lambda **kwargs: {"passed": True, "summary": "ok", "evidence": {}},
    )

    dispatch_task(str(file), search_replace_blocks=[("aaa", "x")])

    assert not isolated_ledger.exists()
