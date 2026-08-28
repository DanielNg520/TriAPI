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

# Real shape of the 2026-08-28 incident that exposed the whole-function-
# deletion blind spot: the item's description names ONLY
# `_is_deepseek_peak_hours` (docstring-only, "do not change any
# implementation logic"), but the diff instead deletes that whole
# function (its hunk anchors to the PRECEDING function,
# `_run_design_judge`, per git's xfuncname heuristic -- the deleted
# function's own `def` line never appears as any hunk header) and
# inlines its logic into `handle_fix_forward`.
_WHOLE_FUNCTION_DELETION_DIFF = """\
diff --git a/scripts/dispatcher.py b/scripts/dispatcher.py
index 2db2cc3..92a34b2 100644
--- a/scripts/dispatcher.py
+++ b/scripts/dispatcher.py
@@ -1012,17 +1012,6 @@ def _run_design_judge(item: dict, result: dict, state: dict, task_id: str) -> di
     return result


-def _is_deepseek_peak_hours(now_utc: time.struct_time | None = None) -> bool:
-    \"\"\"True when the given UTC time (default: now) is inside DeepSeek's peak
-    billing window (06:00-10:00 UTC).\"\"\"
-    return not check_tier3_peak_hours_ok()["ok"]
-
-
 def handle_fix_forward(item: dict, refactor_instruction: str, state: dict, task_id: str) -> dict:
     \"\"\"Invokes Tier 3 to apply the design judge's refactor instructions directly.
     \"\"\"
-    if _is_deepseek_peak_hours():
+    peak_guard = check_tier3_peak_hours_ok()
+    if not peak_guard["ok"]:
         log.warning(
-            "[%s] Tier 3 is in DeepSeek peak billing hours",
+            "[%s] %s",
             task_id,
+            peak_guard["reason"],
         )
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

    def test_whole_function_deletion_is_flagged_via_body_scan(self):
        # Regression for the live 2026-08-28 blind spot: the hunk-header
        # heuristic alone missed this because a fully deleted function's
        # own name never appears as any hunk's header context.
        concerns = scope_guard.find_out_of_scope_functions(
            _WHOLE_FUNCTION_DELETION_DIFF,
            "Update the docstring of _is_deepseek_peak_hours(). "
            "Do not change any implementation logic.",
        )
        self.assertIn("_run_design_judge", concerns)
        self.assertIn("handle_fix_forward", concerns)
        self.assertNotIn("_is_deepseek_peak_hours", concerns)


if __name__ == "__main__":
    unittest.main()
