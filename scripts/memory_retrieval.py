#!/usr/bin/env python3
"""
memory_retrieval.py

Retrieves relevant context for a given task by embedding the task description
and performing cosine-similarity search against a unified RAG index.

Behaviour:
    1. Embed the task description.
    2. If embeddings succeed AND rag_index.build_unified_index(model) yields
       a populated set, perform cosine-similarity ranking with a hard top-K=3
       limit and concatenate them into a final markdown payload.
    3. If embeddings fail or the unified index is unavailable, fall back to:
         - hivemind_util.search_hivemind()
         - lessons.select_relevant()   (keyword-based matching)
    4. Strictly truncate / omit content so the final markdown payload does
       not exceed 4,096 characters (global hard cap).
"""

from __future__ import annotations

import math
import os
import sys
from typing import Any, Iterable, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Optional imports -- degrade gracefully if dependencies are missing.
# ---------------------------------------------------------------------------

try:
    # When run as part of the project, modules live alongside this file.
    from scripts import rag_index  # type: ignore
except Exception:  # pragma: no cover - fallback for ad-hoc execution
    try:
        import rag_index  # type: ignore
    except Exception:
        rag_index = None  # type: ignore[assignment]

try:
    from scripts import hivemind_util  # type: ignore
except Exception:  # pragma: no cover
    try:
        import hivemind_util  # type: ignore
    except Exception:
        hivemind_util = None  # type: ignore[assignment]

try:
    from scripts import lessons  # type: ignore
except Exception:  # pragma: no cover
    try:
        import lessons  # type: ignore
    except Exception:
        lessons = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TOP_K: int = 3
MAX_PAYLOAD_CHARS: int = 4096


# ---------------------------------------------------------------------------
# Embedding helpers
# ---------------------------------------------------------------------------

def _embed_text(text: str, model: str) -> Optional[List[float]]:
    """
    Produce a dense embedding vector for *text* using *model*.

    Returns ``None`` if no embedder is available or the call fails. The intent
    is to be permissive: any failure here simply triggers the keyword fallback
    path further down.
    """
    if not text:
        return None

    # Strategy 1: rag_index exposes an ``embed`` function.
    if rag_index is not None and hasattr(rag_index, "embed"):
        try:
            vec = rag_index.embed(text, model=model)  # type: ignore[attr-defined]
            if vec:
                return [float(x) for x in vec]
        except Exception:
            pass

    # Strategy 2: rag_index exposes a build_unified_index that returns
    # entries with pre-computed embeddings, providing an ``embed_query`` helper.
    if rag_index is not None and hasattr(rag_index, "embed_query"):
        try:
            vec = rag_index.embed_query(text, model=model)  # type: ignore[attr-defined]
            if vec:
                return [float(x) for x in vec]
        except Exception:
            pass

    # Strategy 3: ad-hoc sentence-transformers if installed.
    try:  # pragma: no cover - optional dependency
        from sentence_transformers import SentenceTransformer  # type: ignore

        if not hasattr(_embed_text, "_st_model") or _embed_text._st_model_name != model:  # type: ignore[attr-defined]
            _embed_text._st_model = SentenceTransformer(model)  # type: ignore[attr-defined]
            _embed_text._st_model_name = model  # type: ignore[attr-defined]
        vec = _embed_text._st_model.encode(text).tolist()  # type: ignore[attr-defined]
        return [float(x) for x in vec]
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Similarity helpers
# ---------------------------------------------------------------------------

def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity between two vectors. Returns 0.0 on degenerate input."""
    if not a or not b:
        return 0.0
    if len(a) != len(b):
        # Pad / truncate the shorter vector so dim mismatches don't crash.
        n = min(len(a), len(b))
        a = a[:n]
        b = b[:n]
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def _collect_index_entries(model: str) -> List[Any]:
    """
    Build (or fetch) the unified RAG index and return its entries.

    Each entry is expected to expose at least:
        - ``text`` / ``content`` / ``chunk`` (str)
        - ``embedding`` (Sequence[float]) or ``vector``
        - optional ``source`` / ``metadata`` for nicer rendering.

    Returns an empty list if the index is unavailable or has no entries.
    """
    if rag_index is None or not hasattr(rag_index, "build_unified_index"):
        return []

    try:
        index = rag_index.build_unified_index(model=model)  # type: ignore[attr-defined]
    except Exception:
        return []

    if not index:
        return []

    # Normalise to a list -- some indices may be dicts keyed by id.
    if isinstance(index, dict):
        items: List[Any] = []
        for key, value in index.items():
            if isinstance(value, dict):
                value.setdefault("id", key)
                items.append(value)
            else:
                items.append(value)
        return items

    if isinstance(index, (list, tuple)):
        return list(index)

    # Object with an ``items`` / ``entries`` attribute.
    for attr in ("entries", "items", "docs", "documents"):
        if hasattr(index, attr):
            try:
                value = getattr(index, attr)
                if isinstance(value, (list, tuple)):
                    return list(value)
                if isinstance(value, dict):
                    return [
                        {"id": k, **(v if isinstance(v, dict) else {"content": v})}
                        for k, v in value.items()
                    ]
            except Exception:
                return []
    return []


def _entry_embedding(entry: Any) -> Optional[Sequence[float]]:
    """Extract the embedding vector from an index entry."""
    if entry is None:
        return None
    if isinstance(entry, dict):
        for key in ("embedding", "vector", "embeddings"):
            v = entry.get(key)
            if v:
                return v
        return None
    for attr in ("embedding", "vector", "embeddings"):
        v = getattr(entry, attr, None)
        if v:
            return v
    return None


def _entry_text(entry: Any) -> str:
    """Extract the textual content from an index entry."""
    if entry is None:
        return ""
    if isinstance(entry, dict):
        for key in ("text", "content", "chunk", "body", "page_content"):
            v = entry.get(key)
            if v:
                return str(v)
        return ""
    for attr in ("text", "content", "chunk", "body", "page_content"):
        v = getattr(entry, attr, None)
        if v:
            return str(v)
    return str(entry)


def _entry_metadata(entry: Any) -> dict:
    """Extract metadata (source, score, ...) from an index entry."""
    meta: dict = {}
    if isinstance(entry, dict):
        for key in ("source", "metadata", "id", "score"):
            if key in entry and entry[key] is not None:
                meta[key] = entry[key]
        return meta
    for attr in ("source", "metadata", "id"):
        v = getattr(entry, attr, None)
        if v is not None:
            meta[attr] = v
    return meta


# ---------------------------------------------------------------------------
# Markdown rendering / truncation
# ---------------------------------------------------------------------------

def _format_entry(idx: int, text: str, meta: dict, score: Optional[float] = None) -> str:
    """Render a single retrieval hit as a markdown block."""
    header = f"### Retrieval {idx}"
    if score is not None:
        header += f" (score={score:.4f})"
    src = meta.get("source") or meta.get("id")
    if src:
        header += f" — `{src}`"
    body = text.strip()
    return f"{header}\n\n{body}\n"


def _render_markdown(blocks: Iterable[str]) -> str:
    """Render a list of markdown blocks as a single document."""
    parts = [b for b in blocks if b]
    if not parts:
        return ""
    doc = "\n---\n\n".join(parts)
    return doc.strip() + "\n"


def _enforce_cap(markdown: str, cap: int = MAX_PAYLOAD_CHARS) -> str:
    """
    Strictly truncate *markdown* so its length does not exceed *cap*.

    The hard cap is global -- we never relax it. If the content is too long
    we trim whole sections first, falling back to a hard character slice
    with a trailing note.
    """
    if not markdown:
        return ""
    if len(markdown) <= cap:
        return markdown

    # Try section-wise trimming: split on horizontal rules.
    sections = markdown.split("\n---\n\n")
    kept: List[str] = []
    used = 0
    for sec in sections:
        sec_len = len(sec) + (len("\n---\n\n") if kept else 0)
        if used + sec_len <= cap:
            kept.append(sec)
            used += sec_len
        else:
            remaining = cap - used - (len("\n---\n\n") if kept else 0)
            if remaining > 0:
                kept.append(sec[: max(0, remaining - 1)].rstrip() + "…")
                used += remaining
            break

    out = "\n---\n\n".join(kept).strip()
    if len(out) > cap:
        out = out[: cap - 1].rstrip() + "…"
    return out + "\n"


# ---------------------------------------------------------------------------
# Retrieval paths
# ---------------------------------------------------------------------------

def _rag_retrieval(task_description: str, target_file: str, model: str) -> List[str]:
    """
    Embedding-based retrieval path.

    Returns a list of markdown blocks (one per hit), enforcing top-K=3.
    Returns ``[]`` if embeddings fail or the unified index is empty.
    """
    query_vec = _embed_text(task_description, model=model)
    if not query_vec:
        return []

    entries = _collect_index_entries(model=model)
    if not entries:
        return []

    scored: List[Tuple[float, Any]] = []
    for entry in entries:
        vec = _entry_embedding(entry)
        if not vec:
            continue
        try:
            score = _cosine(query_vec, vec)
        except Exception:
            continue
        scored.append((score, entry))

    if not scored:
        return []

    scored.sort(key=lambda pair: pair[0], reverse=True)
    top = scored[:TOP_K]

    blocks: List[str] = []
    for i, (score, entry) in enumerate(top, start=1):
        text = _entry_text(entry)
        if not text.strip():
            continue
        meta = _entry_metadata(entry)
        blocks.append(_format_entry(i, text, meta, score=score))

    return blocks


def _fallback_retrieval(task_description: str, target_file: str) -> List[str]:
    """
    Keyword-based fallback path. Concatenates results from
    ``hivemind_util.search_hivemind`` and ``lessons.select_relevant``.
    """
    blocks: List[str] = []

    # 1) hivemind search
    if hivemind_util is not None and hasattr(hivemind_util, "search_hivemind"):
        try:
            hits = hivemind_util.search_hivemind(  # type: ignore[attr-defined]
                task_description, target_file=target_file
            )
        except Exception:
            hits = None
        if hits:
            for i, hit in enumerate(hits[:TOP_K], start=1):
                if isinstance(hit, dict):
                    text = hit.get("text") or hit.get("content") or ""
                    meta = {k: v for k, v in hit.items() if k not in {"text", "content"}}
                else:
                    text = str(hit)
                    meta = {}
                if text.strip():
                    blocks.append(_format_entry(i, text, meta))

    # 2) lessons keyword matching
    if lessons is not None and hasattr(lessons, "select_relevant"):
        try:
            lessons_hits = lessons.select_relevant(  # type: ignore[attr-defined]
                task_description, target_file=target_file
            )
        except Exception:
            lessons_hits = None
        if lessons_hits:
            offset = len(blocks) + 1
            for i, hit in enumerate(lessons_hits[:TOP_K], start=offset):
                if isinstance(hit, dict):
                    text = hit.get("text") or hit.get("lesson") or hit.get("content") or ""
                    meta = {k: v for k, v in hit.items() if k not in {"text", "lesson", "content"}}
                else:
                    text = str(hit)
                    meta = {}
                if text.strip():
                    blocks.append(_format_entry(i, text, meta))

    # Re-number to a contiguous 1..TOP_K window if we exceeded the cap.
    if len(blocks) > TOP_K:
        blocks = blocks[:TOP_K]

    return blocks


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def retrieve_context(task_description: str, target_file: str, model: str) -> str:
    """
    Retrieve relevant context for *task_description* and return a markdown
    payload strictly capped at :data:`MAX_PAYLOAD_CHARS` (4,096) characters.

    The retrieval pipeline is:

    1. Embed *task_description* with *model*.
    2. If the embedding succeeds AND ``rag_index.build_unified_index(model)``
       returns an index with embeddings, perform cosine-similarity ranking
       against the index and enforce a hard top-K=3 limit.
    3. Otherwise, fall back to keyword matching via
       ``hivemind_util.search_hivemind`` and ``lessons.select_relevant``.
    4. Concatenate results and apply the global 4,096-character cap.
    """
    # ---- Step 1+2: try the RAG (embedding) path ---------------------------------
    blocks: List[str] = []
    try:
        blocks = _rag_retrieval(task_description, target_file, model)
    except Exception:
        blocks = []

    # ---- Step 3: fall back to keyword search if RAG failed ----------------------
    if not blocks:
        try:
            blocks = _fallback_retrieval(task_description, target_file)
        except Exception:
            blocks = []

    # ---- Step 4: render and enforce the global 4,096-character cap -------------
    doc = _render_markdown(blocks)
    return _enforce_cap(doc, MAX_PAYLOAD_CHARS)


# ---------------------------------------------------------------------------
# CLI entry point -- handy for manual smoke testing.
# ---------------------------------------------------------------------------

def _main(argv: List[str]) -> int:  # pragma: no cover
    if len(argv) < 4:
        print(
            "usage: memory_retrieval.py <task_description> <target_file> <model>",
            file=sys.stderr,
        )
        return 2
    task_description = argv[1]
    target_file = argv[2]
    model = argv[3]
    out = retrieve_context(task_description, target_file, model)
    sys.stdout.write(out)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main(sys.argv))
