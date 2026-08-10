"""Loads and validates config/tiers.yaml and config/resource_guard.yaml."""

from pathlib import Path

import yaml

TIERS_PATH = Path(__file__).resolve().parent.parent / "config" / "tiers.yaml"
RESOURCE_GUARD_PATH = Path(__file__).resolve().parent.parent / "config" / "resource_guard.yaml"

REQUIRED_KEYS = [
    "tier_1_planner",
    "tier_2_manager",
    "tier_3_debugger",
    "tier_4_worker",
    "escalation_rules",
]


def load_tiers(path: Path = TIERS_PATH) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"{path} not found.")

    with open(path) as f:
        config = yaml.safe_load(f)

    missing = [k for k in REQUIRED_KEYS if k not in config]
    if missing:
        raise ValueError(f"{path} is missing required top-level keys: {missing}")

    return config


def load_resource_guard_services(path: Path = RESOURCE_GUARD_PATH) -> list[str]:
    """Machine-specific, optional -- a fresh clone on another machine has no
    such file (or an empty pause_services list), and that's fine: the guard
    just becomes a no-op rather than an error."""
    if not path.exists():
        return []
    with open(path) as f:
        config = yaml.safe_load(f) or {}
    return config.get("pause_services") or []
