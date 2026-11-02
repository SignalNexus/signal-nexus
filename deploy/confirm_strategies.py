"""Fail before SSH unless the checkout strategies file is the expected registry."""

import os
import subprocess
import sys
from pathlib import Path

from app.execution.router import RegistryRejection, load_strategies


def git_blob(path: Path) -> str:
    return subprocess.check_output(["git", "hash-object", str(path)], text=True).strip()


def confirm(path: Path, expected_blob: str) -> str:
    if not path.is_file():
        raise SystemExit("strategies.yml is missing")
    if path.stat().st_size == 0:
        raise SystemExit("strategies.yml is empty")
    catalog = path.parent / "venues.yml"
    previous = os.environ.get("SIGNAL_NEXUS_CONFIG_DIR")
    import app.venues as venues

    previous_registry = venues.REGISTRY_PATH
    if catalog.is_file():
        os.environ["SIGNAL_NEXUS_CONFIG_DIR"] = str(path.parent.resolve())
        venues.REGISTRY_PATH = catalog
    try:
        loaded = load_strategies(path)
    except RegistryRejection as error:
        raise SystemExit(f"strategies.yml rejected: {error}") from error
    finally:
        venues.REGISTRY_PATH = previous_registry
        if previous is None:
            os.environ.pop("SIGNAL_NEXUS_CONFIG_DIR", None)
        else:
            os.environ["SIGNAL_NEXUS_CONFIG_DIR"] = previous
    if not loaded:
        raise SystemExit("strategies.yml is empty")
    blob = git_blob(path)
    if blob != expected_blob:
        raise SystemExit(f"strategies.yml blob {blob} != {expected_blob}")
    return blob


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: confirm_strategies.py PATH EXPECTED_BLOB")
    blob = confirm(Path(sys.argv[1]), sys.argv[2])
    print(f"strategies.yml blob {blob}")


if __name__ == "__main__":
    main()
