import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from scripts.dispatcher import _enforce_module_import_order, _extract_imported_modules


class TestImportOrderGuard(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.repo_root = Path(self.temp_dir.name)
        (self.repo_root / "scripts").mkdir()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_extract_imported_modules_handles_both_import_styles(self):
        # Verify from-style imports and multi-module extraction
        text_from = "from scripts import a, b"
        self.assertEqual(_extract_imported_modules(text_from), {'a', 'b'})

        # Verify import-style imports
        text_import = "import scripts.tech_debt"
        self.assertEqual(_extract_imported_modules(text_import), {'tech_debt'})

    def test_extract_imported_modules_greedy_multiline_behavior(self):
        # Document and assert the known greedy multiline parsing behavior of the regex
        # when no non-whitespace delimiter separates consecutive import statements.
        text_consecutive = "from scripts import a, b\nimport scripts.tech_debt"
        modules = _extract_imported_modules(text_consecutive)
        self.assertEqual(modules, {'a', 'b\nimport scripts'})

        # Introducing a non-whitespace delimiter (like '#') prevents the greedy match.
        text_with_delimiter = "from scripts import a, b\n# delimiter\nimport scripts.tech_debt"
        modules_with_delim = _extract_imported_modules(text_with_delimiter)
        self.assertEqual(modules_with_delim, {'a', 'b', 'tech_debt'})

    def test_reorders_the_exact_2026_08_18_incident_shape(self):
        phase = {
            "items": [
                {"target": "scripts/phase_1.py", "build_cmd": "from scripts import tech_debt"},
                {"target": "scripts/tech_debt.py"}
            ]
        }
        phases = [phase]
        result = _enforce_module_import_order(phases, str(self.repo_root))
        self.assertIsNone(result)
        self.assertEqual(
            phase["items"],
            [
                {"target": "scripts/tech_debt.py"},
                {"target": "scripts/phase_1.py", "build_cmd": "from scripts import tech_debt"},
            ],
        )

    def test_reorders_import_style_dependency(self):
        phase = {
            "items": [
                {"target": "scripts/phase_1.py", "build_cmd": "import scripts.tech_debt"},
                {"target": "scripts/tech_debt.py"},
            ]
        }
        phases = [phase]
        result = _enforce_module_import_order(phases, str(self.repo_root))
        self.assertIsNone(result)
        self.assertEqual(
            phase["items"],
            [
                {"target": "scripts/tech_debt.py"},
                {"target": "scripts/phase_1.py", "build_cmd": "import scripts.tech_debt"},
            ],
        )

    def test_no_violation_leaves_phases_unchanged(self):
        phase = {
            "items": [
                {"target": "scripts/module_a.py"},
                {"build_cmd": "python scripts/module_b.py"}
            ]
        }
        phases = [phase]
        _enforce_module_import_order(phases, str(self.repo_root))
        self.assertEqual(phase["items"], [{"target": "scripts/module_a.py"}, {"build_cmd": "python scripts/module_b.py"}])

    def test_ignores_module_that_already_exists_on_disk(self):
        (self.repo_root / "scripts" / "tech_debt.py").touch()
        phase = {
            "items": [
                {"target": "scripts/phase_1.py", "build_cmd": "from scripts import tech_debt"}
            ]
        }
        phases = [phase]
        result = _enforce_module_import_order(phases, str(self.repo_root))
        self.assertIsNone(result)
        self.assertEqual(
            phase["items"],
            [{"target": "scripts/phase_1.py", "build_cmd": "from scripts import tech_debt"}],
        )

    def test_ignores_git_items(self):
        phase = {
            "items": [
                {"git": {"action": "clone"}, "build_cmd": "python scripts/module_a.py"},
                {"target": "scripts/module_b.py"}
            ]
        }
        phases = [phase]
        _enforce_module_import_order(phases, str(self.repo_root))
        self.assertEqual(phase["items"], [{"git": {"action": "clone"}, "build_cmd": "python scripts/module_a.py"}, {"target": "scripts/module_b.py"}])

    def test_unresolvable_case_returns_error_string(self):
        phase = {
            "items": [
                {"target": "scripts/module_a.py", "build_cmd": "from scripts import module_b"},
                {"target": "scripts/module_b.py", "build_cmd": "from scripts import module_a"}
            ]
        }
        phases = [phase]
        result = _enforce_module_import_order(phases, str(self.repo_root))
        self.assertIsNotNone(result)
        self.assertIn("circular import dependency", result)


if __name__ == "__main__":
    unittest.main()
