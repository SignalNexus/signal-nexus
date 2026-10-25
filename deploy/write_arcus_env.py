import os
import sys

from deploy.envfile import upsert_env


def main() -> None:
    path = sys.argv[1]
    address = os.environ.get("ARCUS_ADDRESS", "").strip()
    secret = os.environ.get("ARCUS_SIGNING_KEY", "").strip()
    if not address or not secret:
        return
    text = upsert_env("", {"ARCUS_ADDRESS": address, "ARCUS_SIGNING_KEY": secret})
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)


if __name__ == "__main__":
    main()
