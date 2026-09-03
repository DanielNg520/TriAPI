"""Tests for _critique_and_maybe_revise_inner revision quality checks.

Split out of tests/test_branch_features.py (which exceeded the 73,728-char
ceiling) to keep both files under the limit; behavior here is independent
of, and does not depend on, other tests in that file.
"""

import unittest
from unittest import mock
import tempfile
from pathlib import Path

from scripts import orchestrator, critique


class CritiqueRevisionQualityChecks(unittest.TestCase):
    """Tests for _critique_and_maybe_revise_inner revision quality checks."""

    def test_revision_below_threshold_gets_reverted(self) -> None:
        """A revision whose rebuild passes but re-critique score is below threshold gets reverted."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target.py"
            # Initial content after a tier fix (must differ from before_content to trigger diff)
            target.write_text("fixed by tier\n", encoding="utf-8")
            before_content = "original\n"

            resolved_target = str(target)

            initial_critique = {"status": "ok", "score": 5, "verdict": "revise", "issues": ["quality issue"]}
            post_revision_critique = {"status": "ok", "score": 4, "verdict": "revise", "issues": ["still bad"]}

            def escalate_fn_mock(*args, **kwargs):
                target.write_text("revised\n", encoding="utf-8")
                return {"status": "fix_applied"}

            with mock.patch('scripts.orchestrator.run_build', return_value=(True, "")):
                with mock.patch('scripts.critique.critique_diff', side_effect=[initial_critique, post_revision_critique]):
                    orchestrator._critique_and_maybe_revise_inner(
                        task_id="test-revert",
                        resolved_target=resolved_target,
                        description="task description",
                        tier_name="tier_3",
                        escalate_fn=escalate_fn_mock,
                        build_cmd="build-command",
                        workdir=tmp,
                        context_blob="context",
                        config={"critique": {"enabled": True, "applies_to_tiers": ["tier_3"], "critic": "tier_1", "max_revision_attempts": 1, "score_threshold": 7}},
                        before_content=before_content,
                    )

            # After function, target should have been reverted to pre-revision content
            self.assertEqual(target.read_text(encoding="utf-8"), "fixed by tier\n")

    def test_revision_clears_threshold_gets_accepted(self) -> None:
        """A revision whose rebuild passes and re-critique score clears the threshold gets accepted."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target.py"
            # Initial content after a tier fix (must differ from before_content to trigger diff)
            target.write_text("fixed by tier\n", encoding="utf-8")
            before_content = "original\n"

            resolved_target = str(target)

            initial_critique = {"status": "ok", "score": 5, "verdict": "revise", "issues": ["quality issue"]}
            post_revision_critique = {"status": "ok", "score": 8, "verdict": "pass", "issues": ["improved"]}

            def escalate_fn_mock(*args, **kwargs):
                target.write_text("revised\n", encoding="utf-8")
                return {"status": "fix_applied"}

            with mock.patch('scripts.orchestrator.run_build', return_value=(True, "")):
                with mock.patch('scripts.critique.critique_diff', side_effect=[initial_critique, post_revision_critique]):
                    orchestrator._critique_and_maybe_revise_inner(
                        task_id="test-accepted",
                        resolved_target=resolved_target,
                        description="task description",
                        tier_name="tier_3",
                        escalate_fn=escalate_fn_mock,
                        build_cmd="build-command",
                        workdir=tmp,
                        context_blob="context",
                        config={"critique": {"enabled": True, "applies_to_tiers": ["tier_3"], "critic": "tier_1", "max_revision_attempts": 1, "score_threshold": 7}},
                        before_content=before_content,
                    )

            # After function, target keeps the revised content (accepted)
            self.assertEqual(target.read_text(encoding="utf-8"), "revised\n")


if __name__ == "__main__":
    unittest.main()
