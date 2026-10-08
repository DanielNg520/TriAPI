"""
Regression tests for leaked edit-block markers.

Incident 2026-10-08: a model reply whose final block nested a second
``<<<<<<< SEARCH`` inside its REPLACE section was applied by
``apply_edit_blocks``, writing the marker line into a repository file.
"""

import unittest

from scripts.edit_blocks import apply_edit_blocks


class TestEditBlocksLeak(unittest.TestCase):
    def test_single_well_formed_block_applies(self) -> None:
        original = "def helper(x):\n    return x\n"
        response = (
            "<<<<<<< SEARCH\n"
            "def helper(x):\n"
            "    return x\n"
            "=======\n"
            "def helper(x):\n"
            "    return x * 2\n"
            ">>>>>>> REPLACE\n"
        )
        new_content, error = apply_edit_blocks(original, response)
        self.assertEqual(error, "")
        self.assertEqual(new_content, "def helper(x):\n    return x * 2\n")

    def test_leaked_search_marker_in_replace_section_rejected(self) -> None:
        original = "def helper(x):\n    return x\n"
        response = (
            "<<<<<<< SEARCH\n"
            "def helper(x):\n"
            "    return x\n"
            "=======\n"
            "<<<<<<< SEARCH\n"
            "def other(page) -> None:\n"
            "    pass\n"
            "\n"
            "def helper(x):\n"
            "    return x\n"
            ">>>>>>> REPLACE\n"
        )
        new_content, error = apply_edit_blocks(original, response)
        self.assertIsNone(new_content)
        self.assertIn("leaked", error.lower())

    def test_leaked_lowercase_search_marker_rejected(self) -> None:
        original = "def helper(x):\n    return x\n"
        response = (
            "<<<<<<< SEARCH\n"
            "def helper(x):\n"
            "    return x\n"
            "=======\n"
            "<<<<<<< search\n"
            "def other(page) -> None:\n"
            "    pass\n"
            "\n"
            "def helper(x):\n"
            "    return x\n"
            ">>>>>>> REPLACE\n"
        )
        new_content, error = apply_edit_blocks(original, response)
        self.assertIsNone(new_content)
        self.assertIn("leaked", error.lower())

    def test_comment_quoting_markers_mid_line_is_preserved(self) -> None:
        original = "def helper(x):\n    return x\n"
        response = "\n".join([
            "<<<<<<< SEARCH",
            "def helper(x):",
            "    return x",
            "=======",
            "    # lines like `<<<<<<< SEARCH` and `>>>>>>> REPLACE` leaked",
            "def helper(x):",
            "    return x",
            ">>>>>>> REPLACE",
        ])
        new_content, error = apply_edit_blocks(original, response)
        self.assertIsNotNone(new_content)
        self.assertEqual(error, "")
        expect = "\n".join([
            "    # lines like `<<<<<<< SEARCH` and `>>>>>>> REPLACE` leaked",
            "def helper(x):",
            "    return x",
        ])
        self.assertIn(expect, new_content)

    def test_marker_as_prose_mid_line_not_rejected(self) -> None:
        original = "def helper(x):\n    return x\n"
        response = (
            "<<<<<<< SEARCH\n"
            "def helper(x):\n"
            "    return x\n"
            "=======\n"
            "Note: >>>>>>> REPLACE is the closing marker.\n"
            "def helper(x):\n"
            "    return x * 2\n"
            ">>>>>>> REPLACE\n"
        )
        new_content, error = apply_edit_blocks(original, response)
        self.assertEqual(error, "")
        self.assertEqual(
            new_content,
            "Note: >>>>>>> REPLACE is the closing marker.\n"
            "def helper(x):\n"
            "    return x * 2\n",
        )

    def test_original_containing_search_marker_can_be_edited(self) -> None:
        original = (
            "<<<<<<< SEARCH\n"
            "def helper(x):\n"
            "    return x\n"
            "=======\n"
            "def helper(x):\n"
            "    return x * 2\n"
            ">>>>>>> REPLACE\n"
        )
        response = (
            "<<<<<<< SEARCH\n"
            "def helper(x):\n"
            "    return x * 2\n"
            "=======\n"
            "def helper(x):\n"
            "    return x * 3\n"
            ">>>>>>> REPLACE\n"
        )
        new_content, error = apply_edit_blocks(original, response)
        self.assertEqual(error, "")
        self.assertEqual(
            new_content,
            "<<<<<<< SEARCH\n"
            "def helper(x):\n"
            "    return x\n"
            "=======\n"
            "def helper(x):\n"
            "    return x * 3\n"
            ">>>>>>> REPLACE\n",
        )


if __name__ == "__main__":
    unittest.main()
