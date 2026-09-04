"""Unit tests for scripts.memory_retrieval covering budget, ranking, and fallback."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock

from scripts import memory_retrieval as mr


class TopKBudgetTests(unittest.TestCase):
    def test_top_k_constant_is_three(self) -> None:
        self.assertEqual(mr.TOP_K, 3)

    def test_max_payload_chars_is_4096(self) -> None:
        self.assertEqual(mr.MAX_PAYLOAD_CHARS, 4096)

    def test_rag_path_caps_output_at_4096_chars(self) -> None:
        # Build an index where every entry is huge so even a single block blows
        # past the budget -- the cap must still hold. _enforce_cap appends a
        # trailing newline, so allow at most one character of slack.
        huge = "x" * 5000
        entries = [
            {"id": f"e{i}", "text": huge, "embedding": [1.0, 0.0, 0.0]}
            for i in range(3)
        ]
        with (
            mock.patch.object(mr, "_embed_text", return_value=[1.0, 0.0, 0.0]),
            mock.patch.object(mr, "_collect_index_entries", return_value=entries),
        ):
            out = mr.retrieve_context("task", "f.py", model="m")
        self.assertLessEqual(len(out), mr.MAX_PAYLOAD_CHARS + 1)
        # The trimmed content (without the trailing newline) must fit the cap.
        if out.endswith("\n"):
            self.assertLessEqual(len(out) - 1, mr.MAX_PAYLOAD_CHARS)

    def test_fallback_path_caps_output_at_4096_chars(self) -> None:
        huge = "y" * 5000

        def fake_search(task_description, target_file):
            return [{"text": huge, "source": "h"} for _ in range(5)]

        with (
            mock.patch.object(mr, "_embed_text", return_value=None),
            mock.patch.object(mr, "_collect_index_entries", return_value=[]),
            mock.patch.object(mr, "hivemind_util", SimpleNamespace(search_hivemind=fake_search)),
        ):
            out = mr.retrieve_context("task", "f.py", model="m")
        self.assertLessEqual(len(out), mr.MAX_PAYLOAD_CHARS + 1)
        if out.endswith("\n"):
            self.assertLessEqual(len(out) - 1, mr.MAX_PAYLOAD_CHARS)

    def test_rag_path_returns_at_most_top_k_blocks(self) -> None:
        entries = [
            {"id": f"e{i}", "text": f"text-{i}", "embedding": [float(i + 1), 0.0, 0.0]}
            for i in range(10)
        ]
        with (
            mock.patch.object(mr, "_embed_text", return_value=[1.0, 0.0, 0.0]),
            mock.patch.object(mr, "_collect_index_entries", return_value=entries),
        ):
            blocks = mr._rag_retrieval("task", "f.py", model="m")
        self.assertEqual(len(blocks), mr.TOP_K)
        # The three highest embeddings win: e2, e1, e0 (sorted by score desc).
        joined = "\n---\n\n".join(blocks)
        self.assertIn("text-2", joined)
        self.assertIn("text-1", joined)
        self.assertIn("text-0", joined)
        self.assertNotIn("text-9", joined)


class CosineSortingTests(unittest.TestCase):
    def test_cosine_identical_vectors_is_one(self) -> None:
        self.assertAlmostEqual(mr._cosine([1.0, 0.0, 0.0], [1.0, 0.0, 0.0]), 1.0)

    def test_cosine_orthogonal_is_zero(self) -> None:
        self.assertAlmostEqual(mr._cosine([1.0, 0.0], [0.0, 1.0]), 0.0)

    def test_cosine_opposite_is_negative_one(self) -> None:
        self.assertAlmostEqual(mr._cosine([1.0, 0.0], [-1.0, 0.0]), -1.0)

    def test_cosine_handles_dim_mismatch(self) -> None:
        # Should not raise; pads/truncates and still returns a number.
        self.assertIsInstance(mr._cosine([1.0, 0.0], [1.0, 0.0, 0.0]), float)

    def test_rag_path_orders_by_cosine_similarity_desc(self) -> None:
        # Query points along +x; the best matches should be those with x>>y.
        query = [1.0, 0.0, 0.0]
        entries = [
            {"id": "low", "text": "low", "embedding": [0.1, 1.0, 0.0]},
            {"id": "high", "text": "high", "embedding": [1.0, 0.5, 0.0]},
            {"id": "mid", "text": "mid", "embedding": [0.5, 0.5, 0.0]},
        ]
        with (
            mock.patch.object(mr, "_embed_text", return_value=query),
            mock.patch.object(mr, "_collect_index_entries", return_value=entries),
        ):
            blocks = mr._rag_retrieval("task", "f.py", model="m")
        # First block must be the highest-scoring entry.
        self.assertIn("high", blocks[0])
        # Scores in the headers should be non-increasing across blocks.
        import re

        scores = []
        for b in blocks:
            m = re.search(r"score=(-?\d+\.\d+)", b)
            self.assertIsNotNone(m, f"missing score in block: {b!r}")
            scores.append(float(m.group(1)))
        self.assertEqual(scores, sorted(scores, reverse=True))


class FallbackTests(unittest.TestCase):
    def test_fallback_when_embeddings_unavailable(self) -> None:
        seen = {"fallback": False}

        def fake_search(task_description, target_file):
            seen["fallback"] = True
            return [{"text": "kw-hit", "source": "hivemind"}]

        # Force both RAG paths to be unusable: embedder returns None and the
        # index yields no entries.
        with (
            mock.patch.object(mr, "_embed_text", return_value=None),
            mock.patch.object(mr, "_collect_index_entries", return_value=[]),
            mock.patch.object(mr, "hivemind_util", SimpleNamespace(search_hivemind=fake_search)),
            mock.patch.object(mr, "lessons", None),
        ):
            out = mr.retrieve_context("task", "f.py", model="m")
        self.assertTrue(seen["fallback"])
        self.assertIn("kw-hit", out)

    def test_fallback_uses_lessons_when_hivemind_empty(self) -> None:
        def fake_search(task_description, target_file):
            return []

        def fake_lessons(task_description, target_file):
            return [{"lesson": "remember this", "source": "lessons.md"}]

        with (
            mock.patch.object(mr, "_embed_text", return_value=None),
            mock.patch.object(mr, "_collect_index_entries", return_value=[]),
            mock.patch.object(mr, "hivemind_util", SimpleNamespace(search_hivemind=fake_search)),
            mock.patch.object(
                mr, "lessons", SimpleNamespace(select_relevant=fake_lessons)
            ),
        ):
            out = mr.retrieve_context("task", "f.py", model="m")
        self.assertIn("remember this", out)

    def test_fallback_truncates_to_top_k(self) -> None:
        # If both sources return more than TOP_K combined, the cap must hold.
        def fake_search(task_description, target_file):
            return [{"text": f"h-{i}", "source": "h"} for i in range(5)]

        def fake_lessons(task_description, target_file):
            return [{"lesson": f"l-{i}", "source": "lessons.md"} for i in range(5)]

        with (
            mock.patch.object(mr, "_embed_text", return_value=None),
            mock.patch.object(mr, "_collect_index_entries", return_value=[]),
            mock.patch.object(mr, "hivemind_util", SimpleNamespace(search_hivemind=fake_search)),
            mock.patch.object(
                mr, "lessons", SimpleNamespace(select_relevant=fake_lessons)
            ),
        ):
            blocks = mr._fallback_retrieval("task", "f.py")
        self.assertEqual(len(blocks), mr.TOP_K)


class EnforceCapTests(unittest.TestCase):
    def test_short_input_is_returned_unchanged(self) -> None:
        self.assertEqual(mr._enforce_cap("hello", cap=10), "hello")

    def test_section_wise_trim_drops_trailing_sections(self) -> None:
        md = "AAA\n---\n\nBBB\n---\n\nCCC"
        # Allow room for AAA + one separator + first 3 chars of BBB, no CCC.
        # The exact split is implementation-defined but the cap must hold.
        # _enforce_cap appends a trailing newline, so allow at most one character of slack.
        out = mr._enforce_cap(md, cap=10)
        self.assertLessEqual(len(out), 11)
        if out.endswith("\n"):
            self.assertLessEqual(len(out) - 1, 10)
        self.assertIn("AAA", out)

    def test_hard_slice_when_sections_still_overflow(self) -> None:
        # One giant block with no separators -- should still be capped.
        # _enforce_cap appends a trailing newline, so allow at most one character of slack.
        md = "X" * 5000
        out = mr._enforce_cap(md, cap=100)
        self.assertLessEqual(len(out), 101)
        if out.endswith("\n"):
            self.assertLessEqual(len(out) - 1, 100)


if __name__ == "__main__":
    unittest.main()
