import ast

from scripts._root_edit_blocks import apply_edit_blocks


def apply_and_verify(original: str, response_text: str) -> tuple[str | None, str | None, str]:
    new_content, err = apply_edit_blocks(original, response_text)
    if err:
        return None, "apply", err

    try:
        ast.parse(new_content)
    except SyntaxError as exc:
        return None, "syntax", str(exc)

    return new_content, None, ""
