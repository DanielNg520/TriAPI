"""Regression tests for scripts.tier4_worker.run_build()'s pipefail fix."""

from __future__ import annotations

import tempfile
import unittest

from scripts.tier4_worker import run_build


class RunBuildPipefailTests(unittest.TestCase):
    def test_piped_failure_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ok, output = run_build("false | tail -1", tmp)
            self.assertIs(ok, False)

    def test_piped_success_still_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ok, output = run_build("true | tail -1", tmp)
            self.assertIs(ok, True)

    def test_ordinary_non_piped_command_unaffected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIs(run_build("true", tmp)[0], True)
            self.assertIs(run_build("false", tmp)[0], False)


if __name__ == "__main__":
    unittest.main()
