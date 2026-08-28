import unittest

from scripts import scope_guard

_IN_SCOPE_ONLY_DIFF = """\
diff --git a/scripts/llm_client.py b/scripts/llm_client.py
index 1111111..2222222 100644
--- a/scripts/llm_client.py
+++ b/scripts/llm_client.py
@@ -206,6 +206,10 @@ def _call_agy_cli(
     prompt: str, model: str | None, effort: str | None, system_prompt: str | None = None
 ) -> Tuple[str, str, int, int]:
+    if len(prompt) > _AGY_MAX_PROMPT_CHARS:
+        raise subprocess.CalledProcessError(0, [], "", "too long")
     if system_prompt:
         prompt = f"{system_prompt}\\n\\n{prompt}"
     cmd = ["agy", "-p", prompt]
"""

_OUT_OF_SCOPE_DIFF = """\
diff --git a/scripts/llm_client.py b/scripts/llm_client.py
index 1111111..2222222 100644
--- a/scripts/llm_client.py
+++ b/scripts/llm_client.py
@@ -185,6 +185,7 @@ def _call_claude_cli(
     prompt: str, system_prompt: str, model: str | None = None, effort: str | None = None
 ) -> Tuple[str, str, int, int]:
+    prompt = prompt.strip()
     cmd = ["claude", "-p", "--system-prompt", system_prompt]
@@ -206,6 +207,10 @@ def _call_agy_cli(
     prompt: str, model: str | None, effort: str | None, system_prompt: str | None = None
 ) -> Tuple[str, str, int, int]:
+    if len(prompt) > _AGY_MAX_PROMPT_CHARS:
+        raise subprocess.CalledProcessError(0, [], "", "too long")
     if system_prompt:
         prompt = f"{system_prompt}\\n\\n{prompt}"
     cmd = ["agy", "-p", prompt]
"""


class TestScopeGuard(unittest.TestCase):
    """Regression coverage for the Tier 3 out-of-scope-edit pattern (queue
    item, 2026-08-28): two confirmed live incidents where Tier 3 rewrote a
    function the item's description never named. This is a heuristic,
    non-blocking flag -- see scope_guard.py's module docstring for why."""

    def test_in_scope_only_diff_is_not_flagged(self):
        concerns = scope_guard.find_out_of_scope_functions(
            _IN_SCOPE_ONLY_DIFF, "Fix the argv-length crash in _call_agy_cli()"
        )
        self.assertEqual(concerns, [])

    def test_out_of_scope_function_is_flagged(self):
        concerns = scope_guard.find_out_of_scope_functions(
            _OUT_OF_SCOPE_DIFF, "Fix the argv-length crash in _call_agy_cli()"
        )
        self.assertEqual(concerns, ["_call_claude_cli"])

    def test_generic_description_naming_no_function_is_not_flagged(self):
        # Description doesn't name any specific function -- can't tell
        # whether this is scoped or not, so don't guess.
        concerns = scope_guard.find_out_of_scope_functions(
            _OUT_OF_SCOPE_DIFF, "Fix the crash in scripts/llm_client.py"
        )
        self.assertEqual(concerns, [])

    def test_diff_with_no_hunk_function_context_is_not_flagged(self):
        diff = (
            "diff --git a/README.md b/README.md\n"
            "index 1111111..2222222 100644\n"
            "--- a/README.md\n"
            "+++ b/README.md\n"
            "@@ -1,3 +1,4 @@\n"
            " # Title\n"
            "+A new line.\n"
        )
        concerns = scope_guard.find_out_of_scope_functions(diff, "Update README.md's title section")
        self.assertEqual(concerns, [])

    def test_empty_diff_is_not_flagged(self):
        self.assertEqual(scope_guard.find_out_of_scope_functions("", "some description"), [])


if __name__ == "__main__":
    unittest.main()
