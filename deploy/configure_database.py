import os
import sys

from deploy.envfile import database_url, read_env, role_sql, upsert_env


def write_database_url(path: str) -> None:
    with open(path, encoding="utf-8") as handle:
        current = handle.read()
    values = read_env(current)
    password = values.get("ANALYTICS_DB_PASSWORD", "")
    if not password:
        raise SystemExit("ANALYTICS_DB_PASSWORD is missing")
    if "MEXC_API_KEY" in values or "MEXC_API_SECRET" in values:
        raise SystemExit("order key must not be on the analytics host")
    updated = upsert_env(current, {"ANALYTICS_DATABASE_URL": database_url(password)})
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(updated)


def write_role_sql(env_path: str, sql_path: str, *, exists: bool) -> None:
    with open(env_path, encoding="utf-8") as handle:
        password = read_env(handle.read()).get("ANALYTICS_DB_PASSWORD", "")
    if not password:
        raise SystemExit("ANALYTICS_DB_PASSWORD is missing")
    fd = os.open(sql_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(role_sql(password, exists=exists))


def main() -> None:
    command = sys.argv[1]
    if command == "database-url":
        write_database_url(sys.argv[2])
        return
    if command == "role-sql":
        write_role_sql(sys.argv[2], sys.argv[3], exists=sys.argv[4] == "exists")
        return
    raise SystemExit("unknown command")


if __name__ == "__main__":
    main()
