import sqlite3

import pytest

from scripts import task_queue as queue


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "queue.sqlite3")
    queue.init_conn(c)
    yield c
    c.close()


def make_args(**kwargs):
    defaults = {"description": None, "worker": None, "depends_on": None,
                "status": None, "id": None, "result": None}
    defaults.update(kwargs)
    return argparse_namespace(**defaults)


def argparse_namespace(**kwargs):
    import argparse
    return argparse.Namespace(**kwargs)


def test_cmd_add_creates_pending_task(conn, capsys):
    args = make_args(description="do the thing", worker="deepseek")
    rc = queue.cmd_add(args, conn)
    assert rc == 0

    task_id = capsys.readouterr().out.strip()
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    assert row["description"] == "do the thing"
    assert row["status"] == "pending"
    assert row["worker"] == "deepseek"

    events = conn.execute(
        "SELECT event_type FROM events WHERE task_id = ?", (task_id,)
    ).fetchall()
    assert [e["event_type"] for e in events] == ["created"]


def test_cmd_list_filters_by_status(conn, capsys):
    queue.cmd_add(make_args(description="a"), conn)
    id_a = capsys.readouterr().out.strip()
    queue.cmd_add(make_args(description="b"), conn)
    conn.execute("UPDATE tasks SET status = 'done' WHERE id != ?", (id_a,))
    capsys.readouterr()

    rc = queue.cmd_list(make_args(status="pending"), conn)
    assert rc == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 1
    assert lines[0].split("\t")[0] == id_a

    rc = queue.cmd_list(make_args(status=None), conn)
    assert rc == 0
    assert len(capsys.readouterr().out.strip().splitlines()) == 2


def test_cmd_approve_pending_to_approved(conn, capsys):
    queue.cmd_add(make_args(description="a"), conn)
    task_id = capsys.readouterr().out.strip()

    rc = queue.cmd_approve(make_args(id=task_id), conn)
    assert rc == 0
    row = conn.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)).fetchone()
    assert row["status"] == "approved"
    events = conn.execute(
        "SELECT event_type FROM events WHERE task_id = ? ORDER BY id", (task_id,)
    ).fetchall()
    assert [e["event_type"] for e in events] == ["created", "approved"]


def test_cmd_approve_rejects_non_pending(conn, capsys):
    queue.cmd_add(make_args(description="a"), conn)
    task_id = capsys.readouterr().out.strip()
    queue.cmd_approve(make_args(id=task_id), conn)

    rc = queue.cmd_approve(make_args(id=task_id), conn)
    assert rc == 1
    row = conn.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)).fetchone()
    assert row["status"] == "approved"


def test_cmd_approve_missing_task(conn):
    rc = queue.cmd_approve(make_args(id="does-not-exist"), conn)
    assert rc == 1


def test_cmd_claim_picks_oldest_approved(conn, capsys):
    queue.cmd_add(make_args(description="first"), conn)
    first_id = capsys.readouterr().out.strip()
    queue.cmd_add(make_args(description="second"), conn)
    second_id = capsys.readouterr().out.strip()
    queue.cmd_approve(make_args(id=first_id), conn)
    queue.cmd_approve(make_args(id=second_id), conn)
    capsys.readouterr()

    rc = queue.cmd_claim(make_args(id=None), conn)
    assert rc == 0
    claimed = capsys.readouterr().out.strip().split("\t")[0]
    assert claimed == first_id
    row = conn.execute("SELECT status FROM tasks WHERE id = ?", (first_id,)).fetchone()
    assert row["status"] == "in_progress"


def test_cmd_claim_respects_depends_on(conn, capsys):
    queue.cmd_add(make_args(description="parent"), conn)
    parent_id = capsys.readouterr().out.strip()
    queue.cmd_add(make_args(description="child", depends_on=parent_id), conn)
    child_id = capsys.readouterr().out.strip()
    queue.cmd_approve(make_args(id=parent_id), conn)
    queue.cmd_approve(make_args(id=child_id), conn)
    capsys.readouterr()

    rc = queue.cmd_claim(make_args(id=child_id), conn)
    assert rc == 1

    queue.cmd_claim(make_args(id=parent_id), conn)
    queue.cmd_complete(make_args(id=parent_id, result="ok", status="done"), conn)
    capsys.readouterr()

    rc = queue.cmd_claim(make_args(id=None), conn)
    assert rc == 0
    claimed = capsys.readouterr().out.strip().split("\t")[0]
    assert claimed == child_id


def test_cmd_claim_rejects_double_claim(conn, capsys):
    queue.cmd_add(make_args(description="a"), conn)
    task_id = capsys.readouterr().out.strip()
    queue.cmd_approve(make_args(id=task_id), conn)
    capsys.readouterr()

    rc1 = queue.cmd_claim(make_args(id=task_id), conn)
    capsys.readouterr()
    rc2 = queue.cmd_claim(make_args(id=task_id), conn)

    assert rc1 == 0
    assert rc2 == 1


def test_cmd_complete_closes_in_progress_task(conn, capsys):
    queue.cmd_add(make_args(description="a"), conn)
    task_id = capsys.readouterr().out.strip()
    queue.cmd_approve(make_args(id=task_id), conn)
    queue.cmd_claim(make_args(id=task_id), conn)
    capsys.readouterr()

    rc = queue.cmd_complete(make_args(id=task_id, result="ok", status="done"), conn)
    assert rc == 0
    row = conn.execute("SELECT status, result FROM tasks WHERE id = ?", (task_id,)).fetchone()
    assert row["status"] == "done"
    assert row["result"] == "ok"
    events = conn.execute(
        "SELECT event_type FROM events WHERE task_id = ? ORDER BY id", (task_id,)
    ).fetchall()
    assert [e["event_type"] for e in events] == ["created", "approved", "claimed", "completed"]


def test_cmd_complete_rejects_non_in_progress(conn, capsys):
    queue.cmd_add(make_args(description="a"), conn)
    task_id = capsys.readouterr().out.strip()

    rc = queue.cmd_complete(make_args(id=task_id, result="ok", status="done"), conn)
    assert rc == 1
    row = conn.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)).fetchone()
    assert row["status"] == "pending"
