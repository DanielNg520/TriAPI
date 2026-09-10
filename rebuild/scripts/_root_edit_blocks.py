"""Bridges to the TriAPI-root scripts/edit_blocks.py despite a package-name
collision: this repo's own `rebuild/scripts` has an __init__.py, so Python
always resolves the name `scripts` to it, never to the TriAPI-root `scripts/`
directory. edit_blocks.py itself has no internal `scripts.` imports, so it
can be loaded directly by file path with no nested-import pre-registration.
"""

import importlib.util
import sys
from pathlib import Path

_TRIAPI_ROOT = Path(__file__).resolve().parent.parent.parent  # rebuild/scripts -> rebuild -> TriAPI
_ROOT_SCRIPTS = _TRIAPI_ROOT / "scripts"


def _load_by_path(module_name: str, file_path: Path):
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_impl = _load_by_path("_root_edit_blocks_impl", _ROOT_SCRIPTS / "edit_blocks.py")

apply_edit_blocks = _impl.apply_edit_blocks
build_edit_prompt_header = _impl.build_edit_prompt_header
EDIT_INSTRUCTION = _impl.EDIT_INSTRUCTION
