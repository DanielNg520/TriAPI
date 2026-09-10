from unittest.mock import MagicMock, patch

import pytest

from scripts.vcb_deepseek_call import make_deepseek_call_fn


def test_first_call_success():
    task_id = "task_test"
    call_fn = make_deepseek_call_fn(task_id)
    mock_result = MagicMock(returncode=0, stdout="response text", stderr="")

    with patch("scripts.vcb_deepseek_call.subprocess.run", return_value=mock_result) as mock_run:
        res = call_fn("test prompt")

        assert res == "response text"
        mock_run.assert_called_once()
        args = mock_run.call_args.args[0]
        assert "--task-id" in args
        idx = args.index("--task-id")
        assert args[idx + 1] == task_id
        assert args[idx + 1] != f"{task_id}_retry"
        assert "--no-fallback" in args


def test_second_call_retry_task_id():
    task_id = "task_test"
    call_fn = make_deepseek_call_fn(task_id)
    mock_result1 = MagicMock(returncode=0, stdout="response 1", stderr="")
    mock_result2 = MagicMock(returncode=0, stdout="response 2", stderr="")

    with patch(
        "scripts.vcb_deepseek_call.subprocess.run",
        side_effect=[mock_result1, mock_result2],
    ) as mock_run:
        call_fn("first prompt")
        call_fn("second prompt")

        assert mock_run.call_count == 2
        second_args = mock_run.call_args_list[1].args[0]
        assert "--task-id" in second_args
        idx = second_args.index("--task-id")
        assert second_args[idx + 1] == f"{task_id}_retry"

        for call in mock_run.call_args_list:
            assert "--no-fallback" in call.args[0]


def test_failure_path_raises_runtime_error():
    task_id = "task_test"
    call_fn = make_deepseek_call_fn(task_id)
    mock_result = MagicMock(returncode=1, stdout="", stderr="some error")

    with patch("scripts.vcb_deepseek_call.subprocess.run", return_value=mock_result) as mock_run:
        with pytest.raises(RuntimeError) as exc_info:
            call_fn("test prompt")

        msg = str(exc_info.value)
        assert "1" in msg
        assert "some error" in msg
        mock_run.assert_called_once()
        args = mock_run.call_args.args[0]
        assert "--no-fallback" in args
