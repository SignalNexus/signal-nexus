"""Clone purchased VenueAdd repositories at the pinned commit.

The token is a fine-grained personal access token stored on the customer's
deploy repository. Git 2.56 asks for a username before it sends an extra
header, so the fetch clears other credential helpers and answers with
username x-access-token and this token as the password. An empty manifest
fetches nothing and does not need a token.
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


def _write_helper(path: Path) -> None:
    path.write_text(
        "#!/bin/sh\n"
        "case \"$1\" in\n"
        "  *get*)\n"
        "    printf '%s\\n' 'username=x-access-token' \"password=$VENUEADD_TOKEN\"\n"
        "    ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def fetch(repository: str, sha: str, dest: Path, token: str) -> None:
    if not token:
        raise SystemExit("venue read token is required")
    if dest.exists():
        raise SystemExit(f"checkout already exists: {dest}")
    dest.mkdir(parents=True)
    fd, name = tempfile.mkstemp(prefix="venueadd-auth-")
    helper = Path(name)
    try:
        os.close(fd)
        _write_helper(helper)
        env = _fetch_env()
        env["VENUEADD_TOKEN"] = token
        _git(["init"], dest)
        _git(["remote", "add", "origin", f"https://github.com/{repository}.git"], dest)
        try:
            _git(
                [
                    "-c",
                    "credential.helper=",
                    "-c",
                    f"credential.helper=!{helper}",
                    "fetch",
                    "--depth",
                    "1",
                    "origin",
                    sha,
                ],
                dest,
                env,
            )
        except subprocess.CalledProcessError:
            raise SystemExit(f"venue repository was not fetched: {repository}") from None
        _git(["checkout", "--detach", "FETCH_HEAD"], dest)
    finally:
        helper.unlink(missing_ok=True)


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
