import pytest

from scripts import tui_session_log


@pytest.fixture(autouse=True)
def sessions_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(tui_session_log, "SESSIONS_DIR", tmp_path / "tui_sessions")
    return tmp_path / "tui_sessions"


def test_new_session_log_path_creates_dir_not_file(sessions_dir):
    path = tui_session_log.new_session_log_path()
    assert sessions_dir.is_dir()
    assert path.parent == sessions_dir
    assert path.suffix == ".md"
    assert not path.exists()


def test_new_session_log_path_avoids_collision(sessions_dir, monkeypatch):
    class FrozenDatetime(tui_session_log.datetime):
        @classmethod
        def now(cls, tz=None):
            return tui_session_log.datetime(2026, 9, 6, 12, 0, 0, tzinfo=tz)

    monkeypatch.setattr(tui_session_log, "datetime", FrozenDatetime)

    first = tui_session_log.new_session_log_path()
    assert first.name == "20260906-120000.md"
    first.write_text("taken")

    second = tui_session_log.new_session_log_path()
    assert second.name == "20260906-120000-2.md"
    assert not second.exists()


def test_format_log_entry_structure():
    entry = tui_session_log.format_log_entry("do X", "did X", "2026-09-06T12:00:00+00:00")
    assert entry.startswith("## 2026-09-06T12:00:00+00:00")
    assert "**Prompt:** do X" in entry
    assert "**Response:**" in entry
    assert entry.rstrip("\n").endswith("did X")
    assert entry.endswith("\n\n")


def test_append_session_log_creates_and_appends(sessions_dir):
    log_path = sessions_dir / "session.md"
    tui_session_log.append_session_log(log_path, "first entry\n\n")
    tui_session_log.append_session_log(log_path, "second entry\n\n")
    content = log_path.read_text()
    assert content == "first entry\n\nsecond entry\n\n"


def test_append_session_log_never_truncates_existing_content(sessions_dir):
    log_path = sessions_dir / "session.md"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("pre-existing\n")
    tui_session_log.append_session_log(log_path, "new\n")
    assert log_path.read_text() == "pre-existing\nnew\n"
