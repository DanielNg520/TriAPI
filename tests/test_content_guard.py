"""Regression tests for scripts.content_guard.check_write's size-ceiling
behavior: refuses authoring a new oversized file or growing an existing
one past MAX_WRITE_CHARS, but allows a write that shrinks an already-
oversized file even if it's still over the ceiling afterward.

Real incident 2026-08-20: a plan pruning a 224KB AGENTS.md down in
several incremental steps had its first, correct, size-reducing edit
refused outright -- the original check treated "still over ceiling" as
disqualifying regardless of direction, deadlocking the exact repair the
ceiling exists to encourage (a file can never be pruned back under the
ceiling if every intermediate, still-over-ceiling-but-smaller state is
refused).
"""

import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from scripts.content_guard import check_write, MAX_WRITE_CHARS


class TestContentGuardSizeCeiling(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.repo_root = Path(self.temp_dir.name)
        self.target_path = self.repo_root / "AGENTS.md"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_refuses_authoring_a_new_oversized_file(self) -> None:
        result = check_write("task1", self.target_path, "x" * (MAX_WRITE_CHARS + 1))
        self.assertFalse(result["ok"])
        self.assertFalse(self.target_path.exists())

    def test_refuses_growing_an_already_oversized_file_further(self) -> None:
        existing = "x" * (MAX_WRITE_CHARS + 100)
        self.target_path.write_text(existing)
        result = check_write("task2", self.target_path, existing + "y" * 500)
        self.assertFalse(result["ok"])

    def test_allows_shrinking_an_oversized_file_even_if_still_over_ceiling(self) -> None:
        existing = "\n".join(f"line {i}" for i in range(1, 20000))
        self.assertGreater(len(existing), MAX_WRITE_CHARS)
        self.target_path.write_text(existing)
        shrunk = "\n".join(f"line {i}" for i in range(1, 15000))
        self.assertGreater(len(shrunk), MAX_WRITE_CHARS)
        self.assertLess(len(shrunk), len(existing))
        result = check_write("task3", self.target_path, shrunk)
        self.assertTrue(result["ok"])

    def test_refuses_oversized_edit_that_does_not_actually_shrink(self) -> None:
        existing = "\n".join(f"line {i}" for i in range(1, 20000))
        self.assertGreater(len(existing), MAX_WRITE_CHARS)
        self.target_path.write_text(existing)
        same_size_rewrite = "\n".join(f"LINE {i}" for i in range(1, 20000))
        self.assertGreaterEqual(len(same_size_rewrite), len(existing))
        result = check_write("task4", self.target_path, same_size_rewrite)
        self.assertFalse(result["ok"])

    def test_ordinary_under_ceiling_write_still_goes_through_retention_check(self) -> None:
        self.target_path.write_text("\n".join(f"line {i}" for i in range(1, 30)))
        result = check_write("task5", self.target_path, "totally different content")
        self.assertFalse(result["ok"])


class TestContentGuardEditBlockMarkerLeak(unittest.TestCase):
    """Real incident 2026-09-01 (run 20260901-135001-dd5f98, oh-my-llama
    Phase 4.1): a fenceless, malformed SEARCH/REPLACE response failed
    edit_blocks.apply_edit_blocks(), the caller's full-file-replacement
    fallback (extract_code() on the same raw response) had no way to
    distinguish that from a genuine fenceless full-file reply, and the
    literal "<<<<<<< SEARCH / ======= / >>>>>>> REPLACE" markup sailed
    through check_write() with no guard at all and landed on disk as a
    trivial new __init__.py's real content."""

    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.repo_root = Path(self.temp_dir.name)
        self.target_path = self.repo_root / "__init__.py"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_refuses_write_containing_raw_search_marker(self) -> None:
        result = check_write(
            "task6", self.target_path,
            "<<<<<<< SEARCH\n\n=======\n>>>>>>> REPLACE\n",
        )
        self.assertFalse(result["ok"])
        self.assertFalse(self.target_path.exists())

    def test_refuses_even_on_a_tiny_new_file_below_the_retention_check_floor(self) -> None:
        # The bug this guards required a target with too few lines to ever
        # reach the retention-ratio check below (MIN_LINES_TO_CHECK) -- an
        # empty/near-empty new file, exactly this shape.
        result = check_write("task7", self.target_path, ">>>>>>> REPLACE\n")
        self.assertFalse(result["ok"])

    def test_ordinary_new_empty_file_still_allowed(self) -> None:
        result = check_write("task8", self.target_path, "")
        self.assertTrue(result["ok"])

    def test_prose_quoting_the_markers_inline_is_allowed(self) -> None:
        # Real false-positive found 2026-09-01/02: a legitimate doc
        # paragraph describing this very incident, quoting both markers
        # inline mid-sentence rather than as real leaked edit-block markup
        # (each marker on its own line). Must not be refused.
        doc_path = self.repo_root / "note.md"
        content = (
            "the literal \"<<<<<<< SEARCH / ======= / >>>>>>> REPLACE\" "
            "markup sailed through check_write() with no guard at all\n"
        )
        result = check_write("task9", doc_path, content)
        self.assertTrue(result["ok"])

    def test_marker_with_trailing_prose_on_same_line_is_allowed(self) -> None:
        # A marker-shaped string followed by other text on the same line
        # is not a real leaked block (real leaks have the marker alone on
        # its own line) -- guards against a regex too loose to tell the
        # difference.
        result = check_write(
            "task10", self.repo_root / "note2.py",
            ">>>>>>> REPLACE is the closing marker for an edit block.\n",
        )
        self.assertTrue(result["ok"])


if __name__ == "__main__":
    unittest.main()
