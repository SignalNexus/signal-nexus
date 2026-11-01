"""Load a deployment manifest. Unknown keys are rejected."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REQUIRED = ("import_name", "repository", "sha", "venue_id", "requirements_file")
FORBIDDEN = frozenset(
    {
        "python_version",
        "secret_name",
        "validation_command",
        "deploy_mode",
        "ssh",
        "systemd",
        "validation_type",
        "package_manager",
        "install_mode",
        "venue_category",
        "post_install",
    }
)
_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SHA = re.compile(r"^[0-9a-f]{40}$")


class ManifestError(ValueError):
    pass


def load_manifest(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict) or set(data) != {"venues"}:
        raise ManifestError("manifest must contain only venues")
    rows = data["venues"] or []
    if not isinstance(rows, list):
        raise ManifestError("venues must be a list")
    loaded: list[dict[str, str]] = []
    seen_imports: set[str] = set()
    seen_ids: set[str] = set()
    for index, row in enumerate(rows, start=1):
        loaded.append(_row(index, row, seen_imports, seen_ids))
    return loaded


def _row(index: int, row: object, seen_imports: set[str], seen_ids: set[str]) -> dict[str, str]:
    if not isinstance(row, dict):
        raise ManifestError(f"venue {index} must be a record")
    extra = set(row) - set(REQUIRED)
    forbidden = sorted(extra & FORBIDDEN)
    if forbidden:
        raise ManifestError(f"venue {index} must not include {forbidden[0]}")
    if extra:
        raise ManifestError(f"venue {index} has an unknown field")
    missing = [key for key in REQUIRED if key not in row]
    if missing:
        raise ManifestError(f"venue {index} is missing {missing[0]}")
    record = {key: str(row[key]).strip() for key in REQUIRED}
    if not _NAME.match(record["import_name"]):
        raise ManifestError(f"venue {index} has a bad import_name")
    if not _REPO.match(record["repository"]):
        raise ManifestError(f"venue {index} has a bad repository")
    if not _SHA.match(record["sha"]):
        raise ManifestError(f"venue {index} has a bad sha")
    if not _NAME.match(record["venue_id"]):
        raise ManifestError(f"venue {index} has a bad venue_id")
    relative = Path(record["requirements_file"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ManifestError(f"venue {index} has a bad requirements_file")
    if record["import_name"] in seen_imports:
        raise ManifestError(f"duplicate import_name: {record['import_name']}")
    if record["venue_id"] in seen_ids:
        raise ManifestError(f"duplicate venue_id: {record['venue_id']}")
    seen_imports.add(record["import_name"])
    seen_ids.add(record["venue_id"])
    return record
