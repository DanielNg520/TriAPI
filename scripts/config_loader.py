"""Loads and validates config/tiers.yaml and config/resource_guard.yaml."""

from pathlib import Path

import yaml

TIERS_PATH = Path(__file__).resolve().parent.parent / "config" / "tiers.yaml"
RESOURCE_GUARD_PATH = Path(__file__).resolve().parent.parent / "config" / "resource_guard.yaml"

REQUIRED_KEYS = [
    "tier_1_planner",
    "tier_1_manager",
    "tier_2_manager",
    "tier_3_debugger",
    "tier_4_worker",
    "escalation_rules",
    "tier_5_librarian",
    "memory_rag",
]


def load_tiers(path: Path = TIERS_PATH) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"{path} not found.")

    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    missing = [k for k in REQUIRED_KEYS if k not in config]
    if missing:
        raise ValueError(f"{path} is missing required top-level keys: {missing}")

    # Validate tier_5_librarian block
    tier_5 = config.get("tier_5_librarian")
    if tier_5 is None:
        raise ValueError(f"{path} is missing required key 'tier_5_librarian'")
    if not isinstance(tier_5, dict):
        raise ValueError(f"{path} 'tier_5_librarian' must be a mapping")
    for subkey in ("models", "target_globs", "max_attempts"):
        if subkey not in tier_5:
            raise ValueError(f"{path} 'tier_5_librarian' missing required sub-key '{subkey}'")
    models = tier_5.get("models")
    if not isinstance(models, dict) or "primary" not in models:
        raise ValueError(f"{path} 'tier_5_librarian' must contain models.primary")

    # Validate memory_rag block
    memory_rag = config.get("memory_rag")
    if memory_rag is None:
        raise ValueError(f"{path} is missing required key 'memory_rag'")
    if not isinstance(memory_rag, dict):
        raise ValueError(f"{path} 'memory_rag' must be a mapping")
    for subkey in ("enabled", "embedding_model"):
        if subkey not in memory_rag:
            raise ValueError(f"{path} 'memory_rag' missing required sub-key '{subkey}'")

    return config


def load_config(path: Path = TIERS_PATH) -> dict:
    """Alias for load_tiers(); returns the full parsed tiers config including
    the memory_rag block (and every other top-level block) so callers can
    access memory_rag via .get('memory_rag', {}).get('embedding_model')."""
    return load_tiers(path)


def load_resource_guard_services(path: Path = RESOURCE_GUARD_PATH) -> list[str]:
    """Machine-specific, optional -- a fresh clone on another machine has no
    such file (or an empty pause_services list), and that's fine: the guard
    just becomes a no-op rather than an error."""
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    return config.get("pause_services") or []

def load_unload_ollama_models_flag(path: Path = RESOURCE_GUARD_PATH) -> bool:
    """Return True if unload_other_ollama_models is true (default), False otherwise."""
    if not path.exists():
        return True
    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    return config.get("unload_other_ollama_models", True)
