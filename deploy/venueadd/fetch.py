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
import tempfile
from pathlib import Path

from deploy.venueadd.manifest import load_manifest

TOKEN_ENV = "VENUEADD_READ_TOKEN"


def _auth_config(token: str) -> str:
    basic = base64.b64encode(f"x-access-token:{token}".encode("ascii")).decode("ascii")
    return (
        "[credential]\n"
        "\thelper =\n"
        '[http "https://github.com"]\n'
        f"\textraheader = AUTHORIZATION: basic {basic}\n"
    )


def _fetch_env(auth_file: Path) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if key
        not in {
            "GIT_ASKPASS",
            "SSH_ASKPASS",
            "GIT_CONFIG_GLOBAL",
            "GIT_CONFIG_SYSTEM",
            "GIT_CONFIG_COUNT",
            "GIT_CONFIG_NOSYSTEM",
            "GIT_CURL_VERBOSE",
        }
        and not key.startswith("GIT_CONFIG_KEY_")
        and not key.startswith("GIT_CONFIG_VALUE_")
        and not key.startswith("GIT_TRACE")
    }
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = str(auth_file)
    return env


def fetch(repository: str, sha: str, dest: Path, token: str) -> None:
    if not token:
        raise SystemExit("venue read token is required")
    if dest.exists():
        raise SystemExit(f"checkout already exists: {dest}")
    dest.mkdir(parents=True)
    fd, name = tempfile.mkstemp(prefix="venueadd-auth-")
    auth = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(_auth_config(token))
        auth.chmod(0o600)
        env = _fetch_env(auth)
        _git(["init"], dest)
        _git(["remote", "add", "origin", f"https://github.com/{repository}.git"], dest)
        try:
            _git(["fetch", "--depth", "1", "origin", sha], dest, env)
        except subprocess.CalledProcessError:
            raise SystemExit(f"venue repository was not fetched: {repository}") from None
        _git(["checkout", "--detach", "FETCH_HEAD"], dest)
    finally:
        auth.unlink(missing_ok=True)


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
