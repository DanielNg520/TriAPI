"""Tests for the unified RAG index builder."""

from __future__ import annotations

import unittest
from unittest import mock

from scripts import rag_index


class BuildUnifiedIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        # Ensure each test starts with a clean module-level cache.
        rag_index._INDEX_CACHE = None

    def test_unifies_both_sources_without_altering_schemas(self) -> None:
        hivemind_chunks = [
            {
                "text": "hivemind snippet one",
                "title": "Pattern A",
                "section": "intro",
                "path": "knowledge/hivemind.md",
                "line": 5,
            },
            {
                "text": "hivemind snippet two",
                "title": "Pattern B",
                "section": "body",
                "path": "knowledge/hivemind.md",
                "line": 20,
            },
        ]
        lessons = [
            {
                "id": "lesson-1",
                "date": "2026-08-12",
                "category": "bug_fix",
                "component": "scripts/edit_blocks.py",
                "tags": ["regex"],
                "bug_description": "BLOCK_RE rejected empty REPLACE blocks.",
            },
            {
                "id": "lesson-2",
                "date": "2026-08-12",
                "category": "bug_fix",
                "component": "scripts/dispatcher.py",
                "tags": ["rpm"],
                "bug_description": "RPM throttling blocked resume.",
                "fix_description": "Use stopped_on_failure.",
            },
        ]

        with mock.patch.object(
            rag_index, "parse_hivemind", return_value=hivemind_chunks
        ), mock.patch.object(
            rag_index, "load_lessons", return_value=lessons
        ), mock.patch.object(
            rag_index, "get_embedding", return_value=[0.1, 0.2, 0.3]
        ):
            index = rag_index.build_unified_index("test-model")

        # Both sources contribute chunks.
        self.assertEqual(len(index["chunks"]), 4)

        # Verify hivemind schema is preserved verbatim and untouched.
        hivemind_entries = [c for c in index["chunks"] if c["metadata"]["source"] == "hivemind"]
        self.assertEqual(len(hivemind_entries), 2)
        for entry, original in zip(hivemind_entries, hivemind_chunks):
            self.assertEqual(entry["text"], original["text"])
            self.assertEqual(entry["metadata"]["title"], original["title"])
            self.assertEqual(entry["metadata"]["section"], original["section"])
            self.assertEqual(entry["metadata"]["path"], original["path"])
            self.assertEqual(entry["metadata"]["line"], original["line"])
            # Original chunk dict should not have been mutated by build.
            self.assertNotIn("metadata", original)

        # Verify lessons schema is preserved verbatim and untouched.
        lesson_entries = [c for c in index["chunks"] if c["metadata"]["source"] == "lessons"]
        self.assertEqual(len(lesson_entries), 2)
        for entry, original in zip(lesson_entries, lessons):
            self.assertEqual(entry["metadata"]["id"], original["id"])
            self.assertEqual(entry["metadata"]["date"], original["date"])
            self.assertEqual(entry["metadata"]["category"], original["category"])
            self.assertEqual(entry["metadata"]["component"], original["component"])
            self.assertEqual(entry["metadata"]["tags"], original["tags"])
            self.assertNotIn("metadata", original)

        # Lessons with fix_description should be appended after "Fix:".
        with_fix = lesson_entries[1]
        self.assertIn("Fix: ", with_fix["text"])
        self.assertTrue(with_fix["text"].endswith("Use stopped_on_failure."))

        # Without fix_description, text equals bug_description verbatim.
        self.assertEqual(lesson_entries[0]["text"], lessons[0]["bug_description"])

        # Counts and metadata are reported correctly.
        self.assertEqual(index["metadata"]["hivemind_chunk_count"], 2)
        self.assertEqual(index["metadata"]["lesson_count"], 2)
        self.assertEqual(index["metadata"]["model"], "test-model")
        self.assertEqual(index["metadata"]["source"], "unified")

    def test_result_is_cached_across_calls(self) -> None:
        with mock.patch.object(
            rag_index, "parse_hivemind", return_value=[]
        ) as parse_mock, mock.patch.object(
            rag_index, "load_lessons", return_value=[]
        ) as lessons_mock, mock.patch.object(
            rag_index, "get_embedding", return_value=[0.0, 0.1]
        ) as embed_mock:
            first = rag_index.build_unified_index("cached-model")
            second = rag_index.build_unified_index("cached-model")

        # Underlying loaders should only run once for the same model.
        parse_mock.assert_called_once()
        lessons_mock.assert_called_once()
        embed_mock.assert_not_called()
        self.assertIs(first, second)
        self.assertEqual(first["metadata"]["model"], "cached-model")
        self.assertEqual(second["metadata"]["model"], "cached-model")

    def test_cache_invalidates_when_model_changes(self) -> None:
        with mock.patch.object(
            rag_index, "parse_hivemind", return_value=[]
        ), mock.patch.object(
            rag_index, "load_lessons", return_value=[]
        ), mock.patch.object(
            rag_index, "get_embedding", return_value=[0.0]
        ):
            first = rag_index.build_unified_index("model-a")
            second = rag_index.build_unified_index("model-b")

        self.assertIsNot(first, second)
        self.assertEqual(first["metadata"]["model"], "model-a")
        self.assertEqual(second["metadata"]["model"], "model-b")

    def test_has_embeddings_false_when_embedding_client_returns_none(self) -> None:
        chunks = [
            {"text": "first", "metadata": {"source": "hivemind"}},
            {"text": "second", "metadata": {"source": "hivemind"}},
            {"text": "third", "metadata": {"source": "lessons"}},
        ]

        def fake_embed(text: str, model: str):
            # Only the middle chunk fails to embed.
            if text == "second":
                return None
            return [0.1, 0.2]

        with mock.patch.object(rag_index, "parse_hivemind", return_value=chunks[:2]), mock.patch.object(
            rag_index, "load_lessons", return_value=[]
        ), mock.patch.object(rag_index, "get_embedding", side_effect=fake_embed):
            index = rag_index.build_unified_index("any-model")

        self.assertFalse(index["has_embeddings"])
        # None is preserved in the embeddings list alongside real vectors.
        self.assertEqual(index["embeddings"][0], [0.1, 0.2])
        self.assertIsNone(index["embeddings"][1])
        self.assertEqual(len(index["embeddings"]), 2)

    def test_has_embeddings_false_when_embedding_client_raises(self) -> None:
        chunks = [
            {"text": "alpha", "metadata": {"source": "hivemind"}},
            {"text": "beta", "metadata": {"source": "lessons"}},
        ]

        def fake_embed(text: str, model: str):
            if text == "beta":
                raise RuntimeError("embedder exploded")
            return [0.5]

        with mock.patch.object(rag_index, "parse_hivemind", return_value=chunks[:1]), mock.patch.object(
            rag_index, "load_lessons", return_value=[
                {
                    "id": "l1",
                    "date": "2026-08-12",
                    "category": "bug_fix",
                    "component": "x.py",
                    "tags": [],
                    "bug_description": "beta",
                }
            ]
        ), mock.patch.object(rag_index, "get_embedding", side_effect=fake_embed):
            index = rag_index.build_unified_index("any-model")

        self.assertFalse(index["has_embeddings"])
        self.assertEqual(index["embeddings"][0], [0.5])
        self.assertIsNone(index["embeddings"][1])

    def test_has_embeddings_true_when_all_succeed(self) -> None:
        with mock.patch.object(
            rag_index, "parse_hivemind", return_value=[]
        ), mock.patch.object(
            rag_index, "load_lessons", return_value=[]
        ), mock.patch.object(
            rag_index, "get_embedding", return_value=[0.0, 0.1]
        ):
            index = rag_index.build_unified_index("ok-model")

        self.assertTrue(index["has_embeddings"])


if __name__ == "__main__":
    unittest.main()
