from scripts.verify import (
    parse_test_output,
    run_test_command,
    verify_file_content,
    verify_scope_boundaries,
    verify_task,
)


def test_parse_test_output_pytest_style():
    assert parse_test_output("5 passed, 1 skipped in 0.12s") == {
        "passed": 5,
        "failed": 0,
        "errors": 0,
        "skipped": 1,
        "total_executed": 5,
    }


def test_parse_test_output_mixed_format_last_wins():
    # A wrapping script prints an early unittest sub-suite summary, then the
    # real final pytest summary later -- the later one must win, not the
    # unittest branch just because it matched first (real bug found live
    # against SemAI's run_tests.sh, 2026-09-05).
    mixed = "Ran 5 tests\nOK\n\nsome other output\n\n10 passed, 2 failed in 1.0s"
    assert parse_test_output(mixed) == {
        "passed": 10,
        "failed": 2,
        "errors": 0,
        "skipped": 0,
        "total_executed": 12,
    }


def test_run_test_command_prefers_stdout_over_noisy_stderr(tmp_path):
    # stderr can carry an unrelated "Ran N tests / OK" line (e.g. a
    # subprocess using unittest's default runner for logging) even though
    # stdout has the real, authoritative final result -- naive
    # stdout+stderr concatenation would let stderr's noise win just because
    # it comes last in the combined string. stdout must be tried first.
    script = tmp_path / "noisy.py"
    script.write_text(
        "import sys\n"
        "print('3 passed in 0.01s')\n"
        "print('Ran 99 tests\\n\\nOK', file=sys.stderr)\n"
    )
    result = run_test_command(["python3", str(script)])
    assert result["counts"]["passed"] == 3
    assert result["passed"] is True


def test_parse_test_output_unittest_style():
    assert parse_test_output(
        "Ran 6 tests in 0.05s\n\nFAILED (failures=1, errors=1, skipped=1)"
    ) == {
        "passed": 3,
        "failed": 1,
        "errors": 1,
        "skipped": 1,
        "total_executed": 5,
    }


def test_run_test_command_zero_executed_fails(tmp_path):
    test_file = tmp_path / "test_skipped.py"
    test_file.write_text(
        "import pytest\n\n\ndef test_skipped():\n    pytest.skip('skip')\n",
        encoding="utf-8",
    )
    result = run_test_command(["python3", "-m", "pytest", "-v", str(test_file)])
    assert result["passed"] is False
    assert result["zero_executed"] is True


def test_run_test_command_real_pass(tmp_path):
    test_file = tmp_path / "test_pass.py"
    test_file.write_text("def test_pass():\n    assert True\n", encoding="utf-8")
    result = run_test_command(["python3", "-m", "pytest", "-v", str(test_file)])
    assert result["passed"] is True


def test_verify_file_content_match_and_mismatch(tmp_path):
    path = tmp_path / "hello.txt"
    path.write_text("hello\n", encoding="utf-8")

    match_result = verify_file_content(path, expected_content="hello\n")
    assert match_result["passed"] is True

    mismatch_result = verify_file_content(path, expected_content="bye\n")
    assert mismatch_result["passed"] is False
    assert any("Content mismatch" in v for v in mismatch_result["violations"])


def test_verify_file_content_missing_file(tmp_path):
    result = verify_file_content(str(tmp_path / "nope.txt"))
    assert result["file_exists"] is False
    assert result["passed"] is False


def test_verify_scope_boundaries_in_and_out_of_scope():
    before = "def foo():\n    return 1\n\n\ndef bar():\n    return 2\n"
    after_bar = "def foo():\n    return 1\n\n\ndef bar():\n    return 3\n"
    after_foo = "def foo():\n    return 4\n\n\ndef bar():\n    return 2\n"

    in_scope = verify_scope_boundaries(before, after_bar, "bar")
    assert in_scope["passed"] is True

    out_of_scope = verify_scope_boundaries(before, after_foo, "bar")
    assert out_of_scope["passed"] is False
    assert any("outside allowed span" in v for v in out_of_scope["violations"])


def test_verify_task_no_checks_fails():
    result = verify_task()
    assert result["passed"] is False
    assert "no checks" in result["summary"].lower()


def test_verify_task_composes_test_run(tmp_path):
    test_file = tmp_path / "test_pass.py"
    test_file.write_text("def test_pass():\n    assert True\n", encoding="utf-8")
    result = verify_task(test_cmd=["python3", "-m", "pytest", "-v", str(test_file)])
    assert result["passed"] is True