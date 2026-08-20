"""Regression test for the sops-encrypted-file edit guard.

Found for real 2026-08-19 dispatching against oh-my-llama: an "investigate
the openclaw 401" item's target was .secret/secrets.json but wasn't marked
verify_only, so Tier 4/3/2 each tried to DRAFT/PATCH the file via the
normal edit_blocks.py SEARCH/REPLACE mechanism -- text-editing sops
ciphertext invalidated the file's MAC (its cryptographic authentication
tag), corrupting it. The underlying encrypted values were untouched
(recovered via `sops -d --ignore-mac`, re-encrypted fresh), but the
corruption itself should never have been possible: no tier should ever be
handed an encrypted file to draft/patch as if it were an ordinary text
file.

Covers scripts.dispatcher._is_sops_encrypted_file (detects a sops file by
its own unencrypted "sops" metadata key, no decryption needed) and
_enforce_no_raw_edits_to_encrypted_files (refuses any non-verify_only,
non-git item targeting one).
"""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.dispatcher import (
    _enforce_no_raw_edits_to_encrypted_files,
    _is_sops_encrypted_file,
)


class TestEncryptedFileEditGuard(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.repo_root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write_sops_file(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "SOME_KEY": "ENC[AES256_GCM,data:abc123,iv:xyz,tag:def]",
            "sops": {"mac": "ENC[...]", "version": "3.8.1"},
        }))

    def _write_plain_file(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"SOME_KEY": "plain value"}))

    def _phases(self, items: list[dict]) -> list[dict]:
        return [{"name": "p", "items": items}]

    def test_is_sops_encrypted_file_true_for_sops_json(self):
        p = self.repo_root / ".secret" / "secrets.json"
        self._write_sops_file(p)
        self.assertTrue(_is_sops_encrypted_file(p))

    def test_is_sops_encrypted_file_false_for_plain_json(self):
        p = self.repo_root / "config.json"
        self._write_plain_file(p)
        self.assertFalse(_is_sops_encrypted_file(p))

    def test_is_sops_encrypted_file_false_for_nonexistent(self):
        p = self.repo_root / "nope.json"
        self.assertFalse(_is_sops_encrypted_file(p))

    def test_guard_rejects_non_verify_only_item_on_encrypted_file(self):
        self._write_sops_file(self.repo_root / ".secret" / "secrets.json")
        phases = self._phases([{
            "target": ".secret/secrets.json",
            "description": "Investigate something",
            "build_cmd": "sops -d .secret/secrets.json",
            "verify_only": False,
        }])
        result = _enforce_no_raw_edits_to_encrypted_files(phases, str(self.repo_root))
        self.assertIsNotNone(result)
        self.assertIn(".secret/secrets.json", result)
        self.assertIn("verify_only", result)

    def test_guard_allows_verify_only_item_on_encrypted_file(self):
        self._write_sops_file(self.repo_root / ".secret" / "secrets.json")
        phases = self._phases([{
            "target": ".secret/secrets.json",
            "description": "Investigate something",
            "build_cmd": "sops -d .secret/secrets.json",
            "verify_only": True,
        }])
        result = _enforce_no_raw_edits_to_encrypted_files(phases, str(self.repo_root))
        self.assertIsNone(result)

    def test_guard_allows_git_item_on_encrypted_file(self):
        self._write_sops_file(self.repo_root / ".secret" / "secrets.json")
        phases = self._phases([{
            "target": ".secret/secrets.json",
            "git": {"action": "pull", "path": "."},
        }])
        result = _enforce_no_raw_edits_to_encrypted_files(phases, str(self.repo_root))
        self.assertIsNone(result)

    def test_guard_allows_non_verify_only_item_on_plain_file(self):
        self._write_plain_file(self.repo_root / "config.json")
        phases = self._phases([{
            "target": "config.json",
            "description": "Edit a normal file",
            "build_cmd": "true",
            "verify_only": False,
        }])
        result = _enforce_no_raw_edits_to_encrypted_files(phases, str(self.repo_root))
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
