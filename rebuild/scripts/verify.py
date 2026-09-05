import ast
import difflib
import re
import subprocess
from pathlib import Path

def parse_test_output(output: str) -> dict[str, int]:
    ran = re.search(r'\bRan\s+(\d+)\s+tests?\b', output)
    if ran:
        total_run = int(ran.group(1))
        failures = errors = skipped = 0
        for kind, value in re.findall(r'\b(failures|errors|skipped)=(\d+)', output):
            if kind == "failures":
                failures = int(value)
            elif kind == "errors":
                errors = int(value)
            else:
                skipped = int(value)
        passed = max(0, total_run - failures - errors - skipped)
        return {
            "passed": passed,
            "failed": failures,
            "errors": errors,
            "skipped": skipped,
            "total_executed": passed + failures + errors,
        }

    counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    for count, kind in re.findall(r'\b(\d+)\s+(passed|failed|errors?|skipped)\b', output):
        count = int(count)
        if kind == "passed":
            counts["passed"] += count
        elif kind == "failed":
            counts["failed"] += count
        elif kind in {"error", "errors"}:
            counts["errors"] += count
        elif kind == "skipped":
            counts["skipped"] += count
    counts["total_executed"] = counts["passed"] + counts["failed"] + counts["errors"]
    return counts


def run_test_command(
    command: str | list[str],
    cwd: str | None = None,
    timeout: int = 120,
) -> dict:
    try:
        result = subprocess.run(
            command,
            shell=isinstance(command, str),
            cwd=cwd,
            timeout=timeout,
            text=True,
            capture_output=True,
        )
        stdout = result.stdout
        stderr = result.stderr
        returncode = result.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0, "total_executed": 0}
        return {
            "passed": False,
            "returncode": -1,
            "counts": counts,
            "zero_executed": True,
            "stdout": stdout,
            "stderr": stderr,
            "error_message": f"Process timed out after {timeout}s",
        }

    counts = parse_test_output(stdout + "\n" + stderr)
    zero_executed = counts["total_executed"] == 0
    passed = (
        returncode == 0
        and counts["failed"] == 0
        and counts["errors"] == 0
        and counts["total_executed"] > 0
    )

    if passed:
        error_message = None
    elif zero_executed:
        error_message = "Zero tests executed"
    else:
        error_message = f"Exit code {returncode} with {counts['failed']} failures, {counts['errors']} errors"

    return {
        "passed": passed,
        "returncode": returncode,
        "counts": counts,
        "zero_executed": zero_executed,
        "stdout": stdout,
        "stderr": stderr,
        "error_message": error_message,
    }


def verify_file_content(
    file_path: str,
    expected_content: str | None = None,
    search_replace_blocks: list[tuple[str, str]] | None = None,
) -> dict:
    path = Path(file_path)
    if not path.exists():
        return {
            "passed": False,
            "file_exists": False,
            "diff": "",
            "violations": [f"File not found: {file_path}"],
        }

    actual_content = path.read_text(encoding="utf-8")
    violations: list[str] = []
    diff = ""

    if expected_content is not None and actual_content != expected_content:
        diff = "\n".join(
            difflib.unified_diff(
                actual_content.splitlines(),
                expected_content.splitlines(),
                lineterm="",
            )
        )
        violations.append("Content mismatch")

    if search_replace_blocks is not None:
        for search_text, replace_text in search_replace_blocks:
            if search_text in actual_content:
                violations.append(f"Search block still present: {search_text!r}")
            if replace_text not in actual_content:
                violations.append(f"Replace block missing: {replace_text!r}")

    return {
        "passed": not violations,
        "file_exists": True,
        "diff": diff,
        "violations": violations,
    }


def verify_scope_boundaries(
    before_content: str,
    after_content: str,
    allowed_function_name: str | None = None,
    allowed_line_range: tuple[int, int] | None = None,
) -> dict:
    before_lines = before_content.splitlines()
    after_lines = after_content.splitlines()

    allowed_range = None
    if allowed_function_name is not None:
        try:
            tree = ast.parse(before_content)
        except SyntaxError:
            allowed_range = None
        else:
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == allowed_function_name:
                    allowed_range = (node.lineno, node.end_lineno)
                    break
    elif allowed_line_range is not None:
        allowed_range = allowed_line_range

    if before_content == after_content:
        return {
            "passed": True,
            "allowed_range": allowed_range,
            "modified_lines": [],
            "violations": [],
            "diff": "\n".join(
                difflib.unified_diff(
                    before_lines,
                    after_lines,
                    fromfile="before",
                    tofile="after",
                    lineterm="",
                )
            ),
        }

    modified_lines = []
    matcher = difflib.SequenceMatcher(None, before_lines, after_lines)
    for tag, _i1, _i2, j1, j2 in matcher.get_opcodes():
        if tag in ("insert", "replace"):
            modified_lines.extend(range(j1 + 1, j2 + 1))

    violations = []
    if allowed_range is not None:
        for line in modified_lines:
            if not (allowed_range[0] <= line <= allowed_range[1]):
                violations.append(f"Line {line} modified outside allowed span {allowed_range}")

    diff = "\n".join(
        difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile="before",
            tofile="after",
            lineterm="",
        )
    )

    return {
        "passed": not violations,
        "allowed_range": allowed_range,
        "modified_lines": modified_lines,
        "violations": violations,
        "diff": diff,
    }


def verify_task(
    file_path: str | None = None,
    before_content: str | None = None,
    expected_content: str | None = None,
    search_replace_blocks: list[tuple[str, str]] | None = None,
    allowed_function_name: str | None = None,
    allowed_line_range: tuple[int, int] | None = None,
    test_cmd: str | list[str] | None = None,
    cwd: str | None = None,
    timeout: int = 120,
) -> dict:
    checks_run = 0
    evidence = {}
    all_passed = True

    if test_cmd is not None:
        checks_run += 1
        evidence["test_run"] = run_test_command(test_cmd, cwd=cwd, timeout=timeout)
        if not evidence["test_run"]["passed"]:
            all_passed = False

    if file_path is not None and (expected_content is not None or search_replace_blocks is not None):
        checks_run += 1
        evidence["content_check"] = verify_file_content(
            file_path, expected_content, search_replace_blocks
        )
        if not evidence["content_check"]["passed"]:
            all_passed = False

    if before_content is not None and (
        allowed_function_name is not None or allowed_line_range is not None
    ):
        with open(file_path, encoding="utf-8") as f:
            after_content = f.read()
        checks_run += 1
        evidence["scope_check"] = verify_scope_boundaries(
            before_content,
            after_content,
            allowed_function_name,
            allowed_line_range,
        )
        if not evidence["scope_check"]["passed"]:
            all_passed = False

    if checks_run == 0:
        return {
            "passed": False,
            "summary": "Verification failed: no checks were supplied",
            "evidence": evidence,
        }

    details = []

    if "test_run" in evidence:
        test_run = evidence["test_run"]
        if test_run["passed"]:
            counts = test_run.get("counts") or {}
            passed_count = counts.get("passed")
            if isinstance(passed_count, int):
                details.append(f"tests: {passed_count} passed")
            else:
                details.append("tests: passed")
        elif test_run.get("zero_executed"):
            details.append("tests: FAILED (Zero tests executed)")
        else:
            details.append("tests: FAILED")

    if "content_check" in evidence:
        if evidence["content_check"]["passed"]:
            details.append("file content: matched")
        else:
            details.append("file content: MISMATCH")

    if "scope_check" in evidence:
        if evidence["scope_check"]["passed"]:
            details.append("scope: intact")
        else:
            details.append("scope: VIOLATED")

    summary_detail = "; ".join(details)

    if all_passed:
        summary = f"All checks passed: {summary_detail}"
    else:
        summary = f"Verification failed: {summary_detail}"

    return {
        "passed": all_passed,
        "summary": summary,
        "evidence": evidence,
    }
