"""Locate author config without treating platform/config as the source."""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_NAMES = (
    "locale.yml",
    "month_target.yml",
    "ops_schedule.yml",
    "strategies.yml",
    "strategy_results.yml",
    "venues.yml",
)


def config_dir() -> Path:
    override = os.environ.get("SIGNAL_NEXUS_CONFIG_DIR")
    if override:
        return Path(override)
    runtime = REPO_ROOT.parent / "ops" / "runtime"
    if (runtime / "venues.yml").is_file():
        return runtime
    return REPO_ROOT / "config"


def config_file(name: str) -> Path:
    return config_dir() / name
