import hashlib
import os
from pathlib import Path

from scripts.verify import verify_task

LEDGER_ENV = "DISPATCH_LEDGER_PATH"


def ledger_path() -> Path:
    return (
        Path(os.environ[LEDGER_ENV])
        if LEDGER_ENV in os.environ
        else Path.home() / ".local" / "state" / "dispatch-ledger" / "applied.sha256"
    )


def record_applied(file_path: str) -> None:
    digest = hashlib.sha256(Path(file_path).read_bytes()).hexdigest()
    ledger = ledger_path()
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a") as f:
        f.write(f"{digest}\n")


RESPONSES_ENV = "DISPATCH_RESPONSES_DIR"


def responses_dir() -> Path:
    return (
        Path(os.environ[RESPONSES_ENV])
        if RESPONSES_ENV in os.environ
        else Path(__file__).resolve().parents[1] / "logs" / "responses"
    )


def store_response(text: str) -> Path:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    directory = responses_dir()
    directory.mkdir(parents=True, exist_ok=True)
    response_path = directory / f"{digest}.txt"
    response_path.write_text(text, encoding="utf-8")
    return response_path


def load_stored_response(path: str | Path) -> str:
    directory = responses_dir().resolve()
    resolved_path = Path(path).resolve()
    if resolved_path.parent != directory:
        raise ValueError("response path is not directly inside the responses directory")
    file_bytes = resolved_path.read_bytes()
    expected_digest = hashlib.sha256(file_bytes).hexdigest()
    if resolved_path.stem != expected_digest:
        raise ValueError("response file stem does not match its content hash")
    return file_bytes.decode("utf-8")


def _line_ending(path: Path) -> str:
    if not path.exists():
        return ""
    return "\r\n" if b"\r\n" in path.read_bytes() else "\n"


def apply_change(
    file_path: str,
    new_content: str | None = None,
    search_replace_blocks: list[tuple[str, str]] | None = None,
) -> str:
    if (new_content is None) == (search_replace_blocks is None):
        raise ValueError("exactly one of new_content or search_replace_blocks must be provided")

    path = Path(file_path)
    raw_bytes = path.read_bytes()
    has_crlf = b"\r\n" in raw_bytes
    has_bare_lf = b"\n" in raw_bytes.replace(b"\r\n", b"")
    if has_crlf and has_bare_lf:
        raise ValueError(f"mixed line endings (both CRLF and LF) in file: {file_path}")

    original = path.read_text(encoding="utf-8")

    if new_content is not None:
        final_content = new_content
    else:
        assert search_replace_blocks is not None
        for search_text, _ in search_replace_blocks:
            count = original.count(search_text)
            if count != 1:
                raise ValueError(
                    f"search_text must appear exactly once, found {count}: {search_text!r}"
                )

        final_content = original
        for search_text, replace_text in search_replace_blocks:
            final_content = final_content.replace(search_text, replace_text, 1)

    path.write_text(final_content, encoding="utf-8", newline=_line_ending(path))
    return original


def restore_file(
    file_path: str,
    original_content: str,
) -> None:
    path = Path(file_path)
    path.write_text(original_content, encoding="utf-8", newline=_line_ending(path))


def dispatch_task(
    file_path: str,
    new_content: str | None = None,
    search_replace_blocks: list[tuple[str, str]] | None = None,
    allowed_function_name: str | None = None,
    allowed_line_range: tuple[int, int] | None = None,
    test_cmd: str | list[str] | None = None,
    cwd: str | None = None,
    timeout: int = 120,
    require_tests: bool = True,
) -> dict:
    try:
        original_content = apply_change(file_path, new_content, search_replace_blocks)
    except (ValueError, FileNotFoundError) as err:
        return {
            "passed": False,
            "summary": f"Dispatch error: {err}",
            "evidence": {"dispatch_error": str(err)},
            "rolled_back": False,
        }

    result = verify_task(
        file_path=file_path,
        before_content=original_content,
        expected_content=new_content,
        search_replace_blocks=search_replace_blocks,
        allowed_function_name=allowed_function_name,
        allowed_line_range=allowed_line_range,
        test_cmd=test_cmd,
        cwd=cwd,
        timeout=timeout,
        require_tests=require_tests,
    )

    if result["passed"] is False:
        restore_file(file_path, original_content)
        return {**result, "rolled_back": True}

    record_applied(file_path)
    return {**result, "rolled_back": False}
