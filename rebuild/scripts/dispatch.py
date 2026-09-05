from pathlib import Path

from scripts.verify import verify_task


def apply_change(
    file_path: str,
    new_content: str | None = None,
    search_replace_blocks: list[tuple[str, str]] | None = None,
) -> str:
    if (new_content is None) == (search_replace_blocks is None):
        raise ValueError("exactly one of new_content or search_replace_blocks must be provided")

    path = Path(file_path)
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

    path.write_text(final_content, encoding="utf-8")
    return original


def restore_file(
    file_path: str,
    original_content: str,
) -> None:
    Path(file_path).write_text(original_content, encoding="utf-8")


def dispatch_task(
    file_path: str,
    new_content: str | None = None,
    search_replace_blocks: list[tuple[str, str]] | None = None,
    allowed_function_name: str | None = None,
    allowed_line_range: tuple[int, int] | None = None,
    test_cmd: str | list[str] | None = None,
    cwd: str | None = None,
    timeout: int = 120,
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
    )

    if result["passed"] is False:
        restore_file(file_path, original_content)
        return {**result, "rolled_back": True}

    return {**result, "rolled_back": False}
