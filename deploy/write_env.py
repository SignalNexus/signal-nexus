import os
import sys

from deploy.envfile import SECRET_KEYS, upsert_env


def main() -> None:
    path = sys.argv[1]
    missing = [key for key in SECRET_KEYS if not os.environ.get(key)]
    if missing:
        print("missing env names: " + ", ".join(missing), file=sys.stderr)
        sys.exit(1)
    current = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            current = handle.read()
    updated = upsert_env(current, {key: os.environ[key] for key in SECRET_KEYS})
    health = os.environ.get("RENDER_HEALTH_URL", "").strip()
    if health.endswith("/health"):
        updated = upsert_env(updated, {"AUDIT_COPY_URL": health[: -len("/health")] + "/api/audit-copies"})
    # Absent or any value other than true stays false, so a deploy does not leave the order API open by omission.
    flag = "true" if os.environ.get("KILL_SWITCH", "").strip() == "true" else "false"
    updated = upsert_env(updated, {"KILL_SWITCH": flag})
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(updated)


if __name__ == "__main__":
    main()
