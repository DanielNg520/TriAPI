"""Snippet parser for triapi snippets in knowledge/hivemind.md.

The knowledge base stores reusable code snippets as raw XML-style
<triapi_snippet> blocks; see knowledge/hivemind.md for the canonical format.
This module parses those blocks into plain dicts for the triapi tooling.
"""

import re
from pathlib import Path

_SNIPPET_RE = re.compile(
    r'<triapi_snippet\b[^>]*\bname="([^"]*)"[^>]*\btags="([^"]*)"[^>]*>(.*?)</triapi_snippet>',
    re.DOTALL,
)


def parse_hivemind(filepath: str = "knowledge/hivemind.md") -> list[dict]:
    """Parse all <triapi_snippet> blocks from the hivemind knowledge file.

    Returns a list of dicts with keys "name" (str), "tags" (list[str]), and
    "code" (str). Returns [] if the file does not exist; the caller is
    expected to treat a missing knowledge base as "no snippets available"
    rather than an error.
    """
    path = Path(filepath)
    if not path.exists():
        return []

    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []

    snippets = []
    for match in _SNIPPET_RE.finditer(text):
        raw_name, raw_tags, code = match.groups()
        name = raw_name.strip()
        if not name:
            continue  # unnamed snippets are not usable; skip them
        tags = [tag.strip() for tag in raw_tags.split(",") if tag.strip()]
        snippets.append({"name": name, "tags": tags, "code": code.strip()})
    return snippets


_EXTENSION_TAG = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".sh": "bash",
    ".md": "markdown",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".html": "html",
    ".css": "css",
    ".rs": "rust",
    ".go": "go",
    ".rb": "ruby",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".cs": "csharp",
    ".php": "php",
    ".sql": "sql",
    ".kt": "kotlin",
    ".swift": "swift",
}


def search_hivemind(task_description: str, file_extension: str) -> str | None:
    """Search hivemind snippets for the best match to a task.

    Snippets are filtered to those tagged with the language corresponding to
    file_extension (e.g. ".py" -> "python"), then scored by how many words in
    task_description appear in the snippet's tag list. The highest-scoring
    snippet's code is returned, or None if nothing matches.
    """
    ext = file_extension.lower()
    if not ext.startswith("."):
        ext = "." + ext
    language = _EXTENSION_TAG.get(ext, ext.lstrip("."))
    words = set(task_description.lower().split())

    best_code = None
    best_score = 0
    for snippet in parse_hivemind():
        if language not in snippet["tags"]:
            continue
        score = sum(1 for word in words if word in snippet["tags"])
        if score > best_score:
            best_score = score
            best_code = snippet["code"]
    return best_code if best_score > 0 else None