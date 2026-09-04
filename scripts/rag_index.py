"""Unified RAG index builder.

Reads hivemind markdown and lessons JSONL, computes embeddings once,
and caches the result for clean fallback signaling when the embedder is
unavailable.
"""

from __future__ import annotations

import threading

from scripts.embedding_client import get_embedding
from scripts.hivemind_util import parse_hivemind
from scripts.lessons import load_lessons


_INDEX_CACHE: dict | None = None
_INDEX_LOCK = threading.Lock()


def build_unified_index(model: str) -> dict:
    """Build (and cache) a unified in-memory index of hivemind + lessons chunks.

    Embeddings are computed exactly once per process run. If any
    ``get_embedding`` call returns ``None`` (embedder unavailable or
    failure), ``has_embeddings`` is set to ``False`` on the returned
    dictionary so callers can signal fallback cleanly.
    """

    global _INDEX_CACHE

    if _INDEX_CACHE is not None and _INDEX_CACHE.get("model") == model:
        return _INDEX_CACHE

    with _INDEX_LOCK:
        if _INDEX_CACHE is not None and _INDEX_CACHE.get("model") == model:
            return _INDEX_CACHE

        chunks: list[dict] = []
        metadata: dict[str, object] = {
            "model": model,
            "source": "unified",
            "hivemind_chunk_count": 0,
            "lesson_count": 0,
        }

        # --- Hivemind markdown ---
        hivemind_chunks = parse_hivemind()
        metadata["hivemind_chunk_count"] = len(hivemind_chunks)
        for ch in hivemind_chunks:
            chunks.append(
                {
                    "text": ch.get("text", ""),
                    "metadata": {
                        "source": "hivemind",
                        "title": ch.get("title"),
                        "section": ch.get("section"),
                        "path": ch.get("path"),
                        "line": ch.get("line"),
                    },
                }
            )

        # --- Lessons JSONL ---
        lessons = load_lessons()
        metadata["lesson_count"] = len(lessons)
        for lesson in lessons:
            text = lesson.get("bug_description", "")
            fix = lesson.get("fix_description", "")
            if fix:
                text = f"{text}\n\nFix: {fix}"
            chunks.append(
                {
                    "text": text,
                    "metadata": {
                        "source": "lessons",
                        "id": lesson.get("id"),
                        "date": lesson.get("date"),
                        "category": lesson.get("category"),
                        "component": lesson.get("component"),
                        "tags": lesson.get("tags", []),
                    },
                }
            )

        # --- Embeddings (compute exactly once; tolerate None) ---
        has_embeddings = True
        embeddings: list[list[float] | None] = []
        for chunk in chunks:
            try:
                vec = get_embedding(chunk["text"], model=model)
            except Exception:
                vec = None
            if vec is None:
                has_embeddings = False
            embeddings.append(vec)

        index: dict[str, object] = {
            "model": model,
            "chunks": chunks,
            "embeddings": embeddings,
            "has_embeddings": has_embeddings,
            "metadata": metadata,
        }

        _INDEX_CACHE = index
        return _INDEX_CACHE
