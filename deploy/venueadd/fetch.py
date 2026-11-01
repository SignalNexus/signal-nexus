"""Clone purchased VenueAdd repositories at the pinned commit."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

from deploy.venueadd.manifest import load_manifest


def fetch(repository: str, sha: str, dest: Path, token: str) -> None:
    if dest.exists():
        raise SystemExit(f"checkout already exists: {dest}")
    dest.mkdir(parents=True)
    askpass = Path(tempfile.mkstemp(prefix="venueadd-askpass-")[1])
    try:
        askpass.write_text('#!/bin/sh\nprintf "%s" "$VENUEADD_TOKEN"\n', encoding="utf-8")
        askpass.chmod(askpass.stat().st_mode | stat.S_IEXEC)
        env = os.environ.copy()
        env["VENUEADD_TOKEN"] = token
        env["GIT_ASKPASS"] = str(askpass)
        env["GIT_TERMINAL_PROMPT"] = "0"
        _git(["init"], dest)
        _git(["remote", "add", "origin", f"https://github.com/{repository}.git"], dest)
        _git(["fetch", "--depth", "1", "origin", sha], dest, env)
        _git(["checkout", "--detach", "FETCH_HEAD"], dest)
    finally:
        askpass.unlink(missing_ok=True)


def fetch_manifest(manifest: Path, dest: Path, token: str) -> None:
    rows = load_manifest(manifest)
    if rows and not token:
        raise SystemExit("checkout token is required")
    for row in rows:
        fetch(row["repository"], row["sha"], dest / row["import_name"], token)


def _git(args: list[str], dest: Path, env: dict[str, str] | None = None) -> None:
    subprocess.run(["git", *args], cwd=dest, check=True, env=env)


def main() -> None:
    manifest = Path(sys.argv[1] if len(sys.argv) > 1 else "venueadd/venues.yaml")
    dest = Path(sys.argv[2] if len(sys.argv) > 2 else "build/venueadd")
    fetch_manifest(manifest, dest, os.environ.get("CHECKOUT_TOKEN", ""))


if __name__ == "__main__":
    main()
