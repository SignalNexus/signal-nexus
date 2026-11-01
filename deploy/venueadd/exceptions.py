"""Core-owned exceptions to venue package metadata."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

_EXCEPTIONS = Path(__file__).with_name("exceptions.yml")
_SPEC = re.compile(
    r"^\s*([A-Za-z0-9][A-Za-z0-9_.-]*)(?:\[[^\]]+\])?==([A-Za-z0-9.*+!]+)\s*(?:#.*)?$"
)


def load_exceptions(path: Path | None = None) -> list[dict[str, object]]:
    raw = yaml.safe_load((path or _EXCEPTIONS).read_text(encoding="utf-8")) or {}
    return list(raw.get("exceptions") or [])


def split_requirements(text: str, exceptions: list[dict[str, object]]) -> tuple[str, list[str]]:
    """Return requirements the solver may see, and pins installed without their dropped deps."""
    kept: list[str] = []
    pins: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("-"):
            kept.append(raw)
            continue
        match = _SPEC.match(stripped)
        if match and _drops(match.group(1), match.group(2), exceptions):
            pins.append(f"{match.group(1)}=={match.group(2)}")
            continue
        kept.append(raw)
    body = "\n".join(kept)
    if body and not body.endswith("\n"):
        body += "\n"
    return body, pins


def _drops(name: str, version: str, exceptions: list[dict[str, object]]) -> bool:
    for item in exceptions:
        if str(item.get("distribution", "")).lower() != name.lower():
            continue
        if str(item.get("version", "")) != version:
            continue
        return bool(item.get("drop_requires"))
    return False
