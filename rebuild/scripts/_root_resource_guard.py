"""Bridges to the TriAPI-root scripts/resource_guard.py (PHASES.md Phase 3's
last unreattached item) despite a package-name collision: this repo's own
`rebuild/scripts` has an __init__.py, so Python always resolves the name
`scripts` to it, never to the TriAPI-root `scripts/` directory (which has no
__init__.py) -- no sys.path ordering trick can change that.

Root's resource_guard.py, unmodified, itself does `from scripts.tri_logging
import get_logger`, assuming `scripts` means the TriAPI-root package. Since
`scripts` is already bound to *this* package by the time anything here runs,
that line would fail. Fix: load tri_logging.py by file path and pre-register
it in sys.modules under the key "scripts.tri_logging" before loading
resource_guard.py the same way -- `from scripts.tri_logging import ...`
resolves straight from the sys.modules cache without needing `scripts`'s own
search path to contain it.
"""

import importlib.util
import sys
from pathlib import Path

import yaml

_TRIAPI_ROOT = Path(__file__).resolve().parent.parent.parent  # rebuild/scripts -> rebuild -> TriAPI
_ROOT_SCRIPTS = _TRIAPI_ROOT / "scripts"
_RESOURCE_GUARD_CONFIG = _TRIAPI_ROOT / "config" / "resource_guard.yaml"


def _load_by_path(module_name: str, file_path: Path):
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_load_by_path("scripts.tri_logging", _ROOT_SCRIPTS / "tri_logging.py")
_impl = _load_by_path("_root_resource_guard_impl", _ROOT_SCRIPTS / "resource_guard.py")

pause_services = _impl.pause_services
resume_services = _impl.resume_services


def load_resource_guard_services() -> list[str]:
    """Same contract as TriAPI-root's scripts/config_loader.py:
    load_resource_guard_services -- machine-specific, optional; a missing
    file or empty pause_services list means the guard is a no-op."""
    if not _RESOURCE_GUARD_CONFIG.exists():
        return []
    with open(_RESOURCE_GUARD_CONFIG, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    return config.get("pause_services") or []
