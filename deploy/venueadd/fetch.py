"""Clone purchased VenueAdd repositories at the pinned commit.

The token is a fine-grained personal access token stored on the customer's
deploy repository. Git sends it as HTTP Basic, with username x-access-token,
and does not consult credential helpers. An empty manifest fetches nothing
and does not need a token.
"""

from __future__ import annotations

import base64
import os
import subprocess
import sys
from pathlib import Path

from deploy.venueadd.manifest import load_manifest

TOKEN_ENV = "VENUEADD_READ_TOKEN"


def _basic_header(token: str) -> str:
    basic = base64.b64encode(f"x-access-token:{token}".encode("ascii")).decode("ascii")
    return f"AUTHORIZATION: basic {basic}"


def _fetch_env() -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if key
        not in {
            "GIT_ASKPASS",
            "SSH_ASKPASS",
            "GIT_CONFIG_COUNT",
            "GIT_CONFIG_NOSYSTEM",
            "GIT_CURL_VERBOSE",
        }
        and not key.startswith("GIT_CONFIG_KEY_")
        and not key.startswith("GIT_CONFIG_VALUE_")
        and not key.startswith("GIT_TRACE")
    }
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def _write_local_header(dest: Path, token: str) -> None:
    config = dest / ".git" / "config"
    config.parent.mkdir(parents=True, exist_ok=True)
    with config.open("a", encoding="utf-8") as handle:
        handle.write(
            '\n[http "https://github.com"]\n'
            f"\textraheader = {_basic_header(token)}\n"
        )
    config.chmod(0o600)


def _strip_local_header(dest: Path) -> None:
    config = dest / ".git" / "config"
    if not config.is_file():
        return
    kept = [
        line
        for line in config.read_text(encoding="utf-8").splitlines(keepends=True)
        if "extraheader" not in line and "AUTHORIZATION:" not in line
    ]
    config.write_text("".join(kept), encoding="utf-8")


def fetch(repository: str, sha: str, dest: Path, token: str) -> None:
    if not token:
        raise SystemExit("venue read token is required")
    if dest.exists():
        raise SystemExit(f"checkout already exists: {dest}")
    dest.mkdir(parents=True)
    _git(["init"], dest)
    _git(["remote", "add", "origin", f"https://github.com/{repository}.git"], dest)
    _write_local_header(dest, token)
    try:
        try:
            _git(
                ["-c", "credential.helper=", "fetch", "--depth", "1", "origin", sha],
                dest,
                _fetch_env(),
            )
        except subprocess.CalledProcessError:
            raise SystemExit(f"venue repository was not fetched: {repository}") from None
        _git(["checkout", "--detach", "FETCH_HEAD"], dest)
    finally:
        _strip_local_header(dest)


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
