"""Clone purchased VenueAdd repositories at the pinned commit.

The token is a fine-grained personal access token stored on the customer's
deploy repository. GitHub allows a fetch only when that customer can read the
repository. An empty manifest fetches nothing and does not need a token.
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

from deploy.venueadd.manifest import load_manifest

TOKEN_ENV = "VENUEADD_READ_TOKEN"


def fetch(repository: str, sha: str, dest: Path, token: str) -> None:
    if not token:
        raise SystemExit("venue read token is required")
    if dest.exists():
        raise SystemExit(f"checkout already exists: {dest}")
    dest.mkdir(parents=True)
    fd, name = tempfile.mkstemp(prefix="venueadd-askpass-")
    askpass = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write('#!/bin/sh\nprintf "%s" "$VENUEADD_TOKEN"\n')
        askpass.chmod(askpass.stat().st_mode | stat.S_IEXEC)
        env = os.environ.copy()
        env["VENUEADD_TOKEN"] = token
        env["GIT_ASKPASS"] = str(askpass)
        env["GIT_TERMINAL_PROMPT"] = "0"
        _git(["init"], dest)
        _git(["remote", "add", "origin", f"https://github.com/{repository}.git"], dest)
        try:
            _git(["fetch", "--depth", "1", "origin", sha], dest, env)
        except subprocess.CalledProcessError:
            raise SystemExit(f"venue repository was not fetched: {repository}") from None
        _git(["checkout", "--detach", "FETCH_HEAD"], dest)
    finally:
        askpass.unlink(missing_ok=True)


def fetch_manifest(manifest: Path, dest: Path, token: str) -> None:
    rows = load_manifest(manifest)
    if not rows:
        return
    if not token:
        raise SystemExit("venue read token is required")
    for row in rows:
        fetch(row["repository"], row["sha"], dest / row["import_name"], token)


def _git(args: list[str], dest: Path, env: dict[str, str] | None = None) -> None:
    subprocess.run(["git", *args], cwd=dest, check=True, env=env)


def main() -> None:
    manifest = Path(sys.argv[1] if len(sys.argv) > 1 else "venueadd/venues.yaml")
    dest = Path(sys.argv[2] if len(sys.argv) > 2 else "build/venueadd")
    fetch_manifest(manifest, dest, os.environ.get(TOKEN_ENV, ""))


if __name__ == "__main__":
    main()
