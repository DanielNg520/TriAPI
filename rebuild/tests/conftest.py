from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    ledger = tmp_path / "applied.sha256"
    monkeypatch.setenv("DISPATCH_LEDGER_PATH", str(ledger))
    monkeypatch.setenv("DISPATCH_RESPONSES_DIR", str(tmp_path / "responses"))
    return ledger

