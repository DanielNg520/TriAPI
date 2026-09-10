from unittest.mock import Mock

import pytest

from scripts.vcb_materializer import (
    build_materializer_prompt,
    build_retry_prompt,
    materialize,
)


def test_build_materializer_prompt():
    file_path = "path/to/file.py"
    file_content = "def foo():\n    pass\n"
    skeleton_draft = "def foo():\n    return 42\n"
    task_description = "Implement foo to return 42"

    prompt = build_materializer_prompt(file_path, file_content, skeleton_draft, task_description)

    assert task_description in prompt
    assert skeleton_draft in prompt
    assert file_content in prompt
    assert "Task:" in prompt
    assert "Local Planner's draft" in prompt
    assert "Current full file content" in prompt


@pytest.mark.parametrize(
    ("error_kind", "expected_heading"),
    [
        ("apply", "This failed to apply:"),
        ("syntax", "Applying this produced invalid Python:"),
        ("other", "This failed:"),
    ],
)
def test_build_retry_prompt(error_kind, expected_heading):
    file_path = "path/to/file.py"
    file_content = "def foo():\n    pass\n"
    previous_response = "<<<<<<< SEARCH\npass\n=======\nreturn 1\n>>>>>>> REPLACE"
    error_message = "Sample error detail"

    prompt = build_retry_prompt(
        file_path, file_content, previous_response, error_kind, error_message
    )

    assert expected_heading in prompt
    assert error_message in prompt
    assert previous_response in prompt
    assert file_content in prompt


def test_materialize_success_first_call():
    original = "def add(a, b):\n    return a + b\n"
    success_response = (
        "<<<<<<< SEARCH\n"
        "    return a + b\n"
        "=======\n"
        "    return a * b\n"
        ">>>>>>> REPLACE"
    )
    call_fn = Mock(return_value=success_response)

    new_content, error_msg = materialize(
        "math.py", original, "def add(a, b): return a * b", "Multiply instead", call_fn
    )

    assert call_fn.call_count == 1
    assert new_content == "def add(a, b):\n    return a * b\n"
    assert error_msg == ""


def test_materialize_retry_success():
    original = "def add(a, b):\n    return a + b\n"
    fail_response = (
        "<<<<<<< SEARCH\n"
        "    return a - b\n"
        "=======\n"
        "    return a * b\n"
        ">>>>>>> REPLACE"
    )
    success_response = (
        "<<<<<<< SEARCH\n"
        "    return a + b\n"
        "=======\n"
        "    return a * b\n"
        ">>>>>>> REPLACE"
    )
    call_fn = Mock(side_effect=[fail_response, success_response])

    new_content, error_msg = materialize(
        "math.py", original, "def add(a, b): return a * b", "Multiply instead", call_fn
    )

    assert call_fn.call_count == 2
    assert new_content == "def add(a, b):\n    return a * b\n"
    assert error_msg == ""


def test_materialize_both_calls_fail():
    original = "def add(a, b):\n    return a + b\n"
    fail_response_1 = (
        "<<<<<<< SEARCH\n"
        "    return a - b\n"
        "=======\n"
        "    return a * b\n"
        ">>>>>>> REPLACE"
    )
    fail_response_2 = (
        "<<<<<<< SEARCH\n"
        "    return a / b\n"
        "=======\n"
        "    return a * b\n"
        ">>>>>>> REPLACE"
    )
    call_fn = Mock(side_effect=[fail_response_1, fail_response_2])

    new_content, error_msg = materialize(
        "math.py", original, "def add(a, b): return a * b", "Multiply instead", call_fn
    )

    assert call_fn.call_count == 2
    assert new_content is None
    assert bool(error_msg)
