import os
import sys

from deploy.envfile import omit_env, read_env, upsert_env


def main() -> None:
    path = sys.argv[1]
    updates = {}
    spot_key = os.environ.get("MEXC_API_KEY", "").strip()
    spot_secret = os.environ.get("MEXC_API_SECRET", "").strip()
    if spot_key and spot_secret:
        updates["MEXC_API_KEY"] = spot_key
        updates["MEXC_API_SECRET"] = spot_secret
    futures_key = os.environ.get("MEXC_FUTURES_API_KEY", "").strip()
    futures_secret = os.environ.get("MEXC_FUTURES_API_SECRET", "").strip()
    if futures_key and futures_secret:
        updates["MEXC_FUTURES_API_KEY"] = futures_key
        updates["MEXC_FUTURES_API_SECRET"] = futures_secret
    try:
        with open(path, encoding="utf-8") as handle:
            current = handle.read()
    except FileNotFoundError:
        current = ""
    if not updates and "DISCORD_WEBHOOK_URL" not in read_env(current):
        return
    text = omit_env(upsert_env(current, updates), {"DISCORD_WEBHOOK_URL"})
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)


if __name__ == "__main__":
    main()
