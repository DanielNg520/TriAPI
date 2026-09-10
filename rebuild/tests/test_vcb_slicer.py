from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.vcb_slicer import (
    build_skeleton,
    extract_import_block,
    parse_single_symbol_output,
    parse_symbols_only_output,
    run_single_symbol,
    run_symbols_only,
)

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "sample_module.py"

SAMPLE_SYMBOLS_ONLY_OUTPUT = """**rebuild/tests/fixtures/sample_module.py** — 4 symbols, no other indexed file depends on it

**Symbols**
- `helper_function` (function) (value) — :6
- `SampleClass` (class) — :10
- `method` (method) (self) — :11
- `target_function` (function) (data) — :15
"""

SAMPLE_SINGLE_SYMBOL_OUTPUT = """**target_function** (function)

**Location:** rebuild/tests/fixtures/sample_module.py:15
**Signature:** `(data)`

```python
15\tdef target_function(data):
16\t    return len(data)
```
"""

SAMPLE_MULTI_MATCH_OUTPUT = """**20 definitions named "main"**
Returning 9 in full; 11 more listed below -- pick the one you need (no Read required).

**main** (function)

**Location:** rebuild/scripts/call_agy.py:24
**Signature:** `() -> int`

```python
24\tdef main() -> int:
25\t    ap = argparse.ArgumentParser(description=__doc__)
```
**Trail — codegraph_node any of these to follow it (no Read needed)**
**Calls →** load_rules (rebuild/scripts/llm_client.py:37)
**Called by ←** call_agy.py (rebuild/scripts/call_agy.py:1)

---

**main** (function)

**Location:** rebuild/scripts/call_deepseek.py:23
**Signature:** `() -> int`

```python
23\tdef main() -> int:
24\t    ap = argparse.ArgumentParser(description=__doc__)
```
**Called by ←** call_deepseek.py (rebuild/scripts/call_deepseek.py:1)

**Other definitions**
- `main` (function) — scripts/cost_report.py:337
- `main` (function) — scripts/jules_client.py:234
"""


def test_extract_import_block_real_fixture():
    result = extract_import_block(str(FIXTURE_PATH))
    assert [line for line in result.splitlines() if line] == [
        "import json",
        "import os",
        "import sys",
    ]


def test_parse_symbols_only_output():
    parsed = parse_symbols_only_output(SAMPLE_SYMBOLS_ONLY_OUTPUT)
    expected = [
        ("helper_function", "(value)", 6),
        ("SampleClass", "", 10),
        ("method", "(self)", 11),
        ("target_function", "(data)", 15),
    ]
    assert parsed == expected


def test_run_symbols_only_success():
    mock_res = MagicMock(returncode=0, stdout=SAMPLE_SYMBOLS_ONLY_OUTPUT, stderr="")
    with patch("scripts.vcb_slicer.subprocess.run", return_value=mock_res) as mock_run:
        result = run_symbols_only(".", str(FIXTURE_PATH))

    mock_run.assert_called_once_with(
        ["codegraph", "node", str(FIXTURE_PATH), "--symbols-only", "-p", "."],
        capture_output=True,
        text=True,
    )
    assert result == [
        ("helper_function", "(value)", 6),
        ("SampleClass", "", 10),
        ("method", "(self)", 11),
        ("target_function", "(data)", 15),
    ]


def test_run_symbols_only_failure():
    mock_res = MagicMock(returncode=1, stdout="", stderr="codegraph error")
    with patch("scripts.vcb_slicer.subprocess.run", return_value=mock_res):
        with pytest.raises(RuntimeError, match="codegraph node failed with return code 1"):
            run_symbols_only(".", str(FIXTURE_PATH))


def test_parse_single_symbol_output_success():
    result = parse_single_symbol_output(SAMPLE_SINGLE_SYMBOL_OUTPUT)
    assert result == "def target_function(data):\n    return len(data)"


def test_parse_single_symbol_output_multi_match_raises():
    with pytest.raises(ValueError, match="multi-match listing"):
        parse_single_symbol_output(SAMPLE_MULTI_MATCH_OUTPUT)


def test_run_single_symbol_success():
    mock_res = MagicMock(returncode=0, stdout=SAMPLE_SINGLE_SYMBOL_OUTPUT, stderr="")
    with patch("scripts.vcb_slicer.subprocess.run", return_value=mock_res) as mock_run:
        result = run_single_symbol(".", "target_function")

    mock_run.assert_called_once_with(
        ["codegraph", "node", "target_function", "-p", "."],
        capture_output=True,
        text=True,
    )
    assert result == "def target_function(data):\n    return len(data)"


def test_run_single_symbol_failure():
    mock_res = MagicMock(returncode=1, stdout="", stderr="codegraph error")
    with patch("scripts.vcb_slicer.subprocess.run", return_value=mock_res):
        with pytest.raises(RuntimeError, match="codegraph node failed with return code 1"):
            run_single_symbol(".", "target_function")


def test_build_skeleton_end_to_end():
    with patch(
        "scripts.vcb_slicer.run_symbols_only",
        return_value=[
            ("helper_function", "(value)", 6),
            ("SampleClass", "", 10),
            ("method", "(self)", 11),
            ("target_function", "(data)", 15),
        ],
    ), patch(
        "scripts.vcb_slicer.run_single_symbol",
        return_value="def target_function(data):\n    return len(data)",
    ):
        skeleton = build_skeleton(".", str(FIXTURE_PATH), "target_function")

    assert "import json\nimport os\nimport sys" in skeleton

    helper_entry = "helper_function(value):\n    ...\n"
    sample_class_entry = "SampleClass:\n    ...\n"
    target_source = "def target_function(data):\n    return len(data)"

    assert helper_entry in skeleton
    assert sample_class_entry in skeleton
    assert target_source in skeleton

    import_idx = skeleton.index("import json")
    helper_idx = skeleton.index(helper_entry)
    sample_class_idx = skeleton.index(sample_class_entry)
    target_idx = skeleton.index(target_source)

    assert import_idx < helper_idx < sample_class_idx < target_idx


def test_build_skeleton_missing_target_raises():
    with patch(
        "scripts.vcb_slicer.run_symbols_only",
        return_value=[
            ("helper_function", "(value)", 6),
            ("SampleClass", "", 10),
        ],
    ):
        with pytest.raises(ValueError, match="Target symbol 'unknown_func' not found"):
            build_skeleton(".", str(FIXTURE_PATH), "unknown_func")
