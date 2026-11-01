"""Fail before SSH unless the checkout strategies file is the expected registry."""

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
    try:
        loaded = load_strategies(path)
    except RegistryRejection as error:
        raise SystemExit(f"strategies.yml rejected: {error}") from error
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
