import sqlite3

import pytest

from scripts import tui


@pytest.fixture(autouse=True)
def sessions_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(tui, "SESSIONS_DIR", tmp_path / "tui_sessions")
    return tmp_path / "tui_sessions"


def test_new_session_log_path_creates_dir_not_file(sessions_dir):
    path = tui.new_session_log_path()
    assert sessions_dir.is_dir()
    assert path.parent == sessions_dir
    assert path.suffix == ".md"
    assert not path.exists()


def test_new_session_log_path_avoids_collision(sessions_dir, monkeypatch):
    class FrozenDatetime(tui.datetime):
        @classmethod
        def now(cls, tz=None):
            return tui.datetime(2026, 9, 6, 12, 0, 0, tzinfo=tz)

    monkeypatch.setattr(tui, "datetime", FrozenDatetime)

    first = tui.new_session_log_path()
    assert first.name == "20260906-120000.md"
    first.write_text("taken")

    second = tui.new_session_log_path()
    assert second.name == "20260906-120000-2.md"
    assert not second.exists()


def test_build_framed_prompt_prefixes_and_preserves_raw():
    raw = "claim the next task and dispatch it"
    framed = tui.build_framed_prompt(raw)
    assert framed.startswith(tui.FRAMING_PREFIX)
    assert framed.endswith(raw)
    assert raw in framed


def test_format_log_entry_structure():
    entry = tui.format_log_entry("do X", "did X", "2026-09-06T12:00:00+00:00")
    assert entry.startswith("## 2026-09-06T12:00:00+00:00")
    assert "**Prompt:** do X" in entry
    assert "**Response:**" in entry
    assert entry.rstrip("\n").endswith("did X")
    assert entry.endswith("\n\n")


def test_append_session_log_creates_and_appends(sessions_dir):
    log_path = sessions_dir / "session.md"
    tui.append_session_log(log_path, "first entry\n\n")
    tui.append_session_log(log_path, "second entry\n\n")
    content = log_path.read_text()
    assert content == "first entry\n\nsecond entry\n\n"


def test_append_session_log_never_truncates_existing_content(sessions_dir):
    log_path = sessions_dir / "session.md"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("pre-existing\n")
    tui.append_session_log(log_path, "new\n")
    assert log_path.read_text() == "pre-existing\nnew\n"


@pytest.fixture
def queue_db(tmp_path, monkeypatch):
    db_path = tmp_path / "queue.sqlite3"
    monkeypatch.setattr(tui, "DB_PATH", db_path)
    return db_path


def test_is_dispatch_running_false_when_db_missing(queue_db):
    assert tui.is_dispatch_running() is False


def test_is_dispatch_running_false_when_no_in_progress_task(queue_db):
    from scripts import task_queue as queue

    conn = sqlite3.connect(queue_db)
    queue.init_conn(conn)
    conn.execute(
        "INSERT INTO tasks (id, description, status, worker, depends_on, result, "
        "created_at, updated_at) VALUES ('t1', 'x', 'pending', NULL, NULL, NULL, 'ts', 'ts')"
    )
    conn.commit()
    conn.close()

    assert tui.is_dispatch_running() is False


def test_is_dispatch_running_true_when_in_progress_task_exists(queue_db):
    from scripts import task_queue as queue

    conn = sqlite3.connect(queue_db)
    queue.init_conn(conn)
    conn.execute(
        "INSERT INTO tasks (id, description, status, worker, depends_on, result, "
        "created_at, updated_at) VALUES ('t1', 'x', 'in_progress', NULL, NULL, NULL, 'ts', 'ts')"
    )
    conn.commit()
    conn.close()

    assert tui.is_dispatch_running() is True


class _FakeStdout:
    def __init__(self, lines):
        self._lines = iter(lines)

    def __iter__(self):
        return self

    def __next__(self):
        return next(self._lines)


class _FakeProcess:
    def __init__(self, lines):
        self.stdout = _FakeStdout(lines)
        self.waited = False

    def wait(self):
        self.waited = True


def test_stream_claude_output_yields_lines_and_strips_newline(monkeypatch):
    fake_proc = _FakeProcess(["line one\n", "line two\n"])

    def fake_popen(cmd, stdout=None, stderr=None, text=None):
        assert cmd == ["claude", "-p", "hello"]
        return fake_proc

    monkeypatch.setattr(tui.subprocess, "Popen", fake_popen)

    lines = list(tui.stream_claude_output("hello"))
    assert lines == ["line one", "line two"]
    assert fake_proc.waited is True


def test_stream_claude_output_stops_cleanly_on_empty_output(monkeypatch):
    fake_proc = _FakeProcess([])
    monkeypatch.setattr(tui.subprocess, "Popen", lambda *a, **k: fake_proc)

    assert list(tui.stream_claude_output("hello")) == []
