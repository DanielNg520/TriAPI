from scripts._root_edit_blocks import build_edit_prompt_header
from scripts.vcb_patcher import apply_and_verify


def build_materializer_prompt(file_path: str, file_content: str, skeleton_draft: str, task_description: str) -> str:
    header = build_edit_prompt_header(file_path)
    return f"""{header}

Task:
{task_description}

Local Planner's draft (correctness reference only -- do not copy verbatim, integrate it into the real file structure and conventions below):
{skeleton_draft}

Current full file content (`{file_path}`):
```
{file_content}
```"""


def build_retry_prompt(file_path: str, file_content: str, previous_response: str, error_kind: str, error_message: str) -> str:
    header = build_edit_prompt_header(file_path)
    if error_kind == "apply":
        failure = f"""This failed to apply: {error_message}
Make sure the SEARCH text matches the current file EXACTLY and is unique."""
    elif error_kind == "syntax":
        failure = f"""Applying this produced invalid Python: {error_message}
Fix the REPLACE text so the resulting file is syntactically valid."""
    else:
        failure = f"""This failed: {error_message}"""
    return f"""{header}

Your previous SEARCH/REPLACE response:
```
{previous_response}
```

{failure}

Current full file content (`{file_path}`), for reference -- your new SEARCH text must match this exactly:
```
{file_content}
```"""


def materialize(file_path: str, file_content: str, skeleton_draft: str, task_description: str, call_fn) -> tuple[str | None, str]:
    prompt = build_materializer_prompt(file_path, file_content, skeleton_draft, task_description)
    response = call_fn(prompt)

    new_content, error_kind, error_message = apply_and_verify(file_content, response)
    if error_kind is None:
        return new_content, ""

    retry_prompt = build_retry_prompt(file_path, file_content, response, error_kind, error_message)
    retry_response = call_fn(retry_prompt)

    retry_new_content, retry_error_kind, retry_error_message = apply_and_verify(file_content, retry_response)
    if retry_error_kind is None:
        return retry_new_content, ""

    return None, retry_error_message
