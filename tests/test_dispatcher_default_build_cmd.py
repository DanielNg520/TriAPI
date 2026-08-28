import unittest

from scripts import dispatcher


class TestDefaultBuildCmd(unittest.TestCase):
    """Regression coverage for the py_compile-insufficient verify-command
    gap (queue item 3, 2026-08-28): a test file target's default build_cmd
    must actually import/collect the module (catching a hallucinated
    import or nonexistent function reference), not just syntax-check it --
    confirmed live twice that py_compile alone let a fabricated test file
    report success."""

    def test_test_file_target_uses_unittest_not_py_compile(self):
        cmd = dispatcher._default_build_cmd("tests/test_foo.py")
        self.assertNotIn("py_compile", cmd)
        self.assertIn("unittest", cmd)
        self.assertIn("tests.test_foo", cmd)

    def test_non_test_python_file_still_uses_py_compile(self):
        cmd = dispatcher._default_build_cmd("scripts/foo.py")
        self.assertIn("py_compile", cmd)
        self.assertIn("scripts/foo.py", cmd)

    def test_non_python_file_uses_existence_check(self):
        cmd = dispatcher._default_build_cmd("docs/foo.md")
        self.assertIn("test -f", cmd)
        self.assertIn("docs/foo.md", cmd)


if __name__ == "__main__":
    unittest.main()
