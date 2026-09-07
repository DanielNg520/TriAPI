import sqlite3

import pytest

from scripts import tui_dispatch_status


@pytest.fixture
def queue_db(tmp_path, monkeypatch):
    db_path = tmp_path / "queue.sqlite3"
    monkeypatch.setattr(tui_dispatch_status, "DB_PATH", db_path)
    return db_path


def test_is_dispatch_running_false_when_db_missing(queue_db):
    assert tui_dispatch_status.is_dispatch_running() is False


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

    assert tui_dispatch_status.is_dispatch_running() is False


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

    assert tui_dispatch_status.is_dispatch_running() is True
