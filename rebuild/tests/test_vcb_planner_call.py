import sys
from unittest.mock import MagicMock, patch

import pytest

from scripts.vcb_planner_call import make_planner_call_fn


def test_first_call_success():
    task_id = "task_test"
    system_file = "system_prompt.txt"
    call_fn = make_planner_call_fn(task_id, system_file)
    mock_result = MagicMock(returncode=0, stdout="response text", stderr="")

    with patch("scripts.vcb_planner_call.subprocess.run", return_value=mock_result) as mock_run:
        res = call_fn("test prompt")

        assert res == "response text"
        mock_run.assert_called_once()
        args = mock_run.call_args.args[0]
        assert args[0] == sys.executable
        assert "--system-file" in args
        idx = args.index("--system-file")
        assert args[idx + 1] == system_file
        assert "--task-id" in args
        idx = args.index("--task-id")
        assert args[idx + 1] == task_id
        kwargs = mock_run.call_args.kwargs
        assert kwargs["input"] == "test prompt"


def test_second_invocation_uses_retry_task_id():
    task_id = "task_test"
    system_file = "system_prompt.txt"
    call_fn = make_planner_call_fn(task_id, system_file)
    mock_result = MagicMock(returncode=0, stdout="", stderr="")

    with patch("scripts.vcb_planner_call.subprocess.run", return_value=mock_result) as mock_run:
        call_fn("first prompt")
        call_fn("second prompt")

        assert mock_run.call_count == 2
        second_args = mock_run.call_args_list[1].args[0]
        idx = second_args.index("--task-id")
        assert second_args[idx + 1] == f"{task_id}_retry"
        assert mock_run.call_args_list[1].kwargs["input"] == "second prompt"


def test_nonzero_return_code_raises_runtime_error():
    task_id = "task_test"
    system_file = "system_prompt.txt"
    call_fn = make_planner_call_fn(task_id, system_file)
    mock_result = MagicMock(returncode=3, stdout="", stderr="planner exploded")

    with patch("scripts.vcb_planner_call.subprocess.run", return_value=mock_result):
        with pytest.raises(RuntimeError) as exc_info:
            call_fn("bad prompt")

        message = str(exc_info.value)
        assert "3" in message
        assert "planner exploded" in message


def test_zero_return_code_returns_stdout_unmodified():
    task_id = "task_test"
    system_file = "system_prompt.txt"
    call_fn = make_planner_call_fn(task_id, system_file)
    stdout = "exact stdout\nwith newline"
    mock_result = MagicMock(returncode=0, stdout=stdout, stderr="")

    with patch("scripts.vcb_planner_call.subprocess.run", return_value=mock_result):
        assert call_fn("prompt") == stdout
