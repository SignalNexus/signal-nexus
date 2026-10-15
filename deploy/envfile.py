def env_assignment(key: str, value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'{key}="{escaped}"'


def read_env(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
            value = value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        values[key] = value
    return values


def upsert_env(text: str, updates: dict[str, str]) -> str:
    lines: list[str] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        stripped = raw.strip()
        key = stripped.split("=", 1)[0] if stripped and not stripped.startswith("#") and "=" in stripped else ""
        if key in updates:
            lines.append(env_assignment(key, updates[key]))
            seen.add(key)
        else:
            lines.append(raw)
    for key, value in updates.items():
        if key not in seen:
            lines.append(env_assignment(key, value))
    body = "\n".join(lines)
    if body and not body.endswith("\n"):
        body += "\n"
    if not body:
        body = "\n"
    return body


def omit_env(text: str, keys: set[str]) -> str:
    lines: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        key = stripped.split("=", 1)[0] if stripped and not stripped.startswith("#") and "=" in stripped else ""
        if key in keys:
            continue
        lines.append(raw)
    body = "\n".join(lines)
    if body and not body.endswith("\n"):
        body += "\n"
    if not body:
        body = "\n"
    return body


def database_url(password: str) -> str:
    from urllib.parse import quote

    return f"postgresql://signalnexus:{quote(password, safe='')}@127.0.0.1:5432/signalnexus"


def quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def role_sql(password: str, *, exists: bool) -> str:
    literal = quote_literal(password)
    if exists:
        statement = f"ALTER ROLE signalnexus WITH LOGIN PASSWORD {literal};"
    else:
        statement = f"CREATE ROLE signalnexus LOGIN PASSWORD {literal};"
    return statement + "\n"


SECRET_KEYS = (
    "ANALYTICS_API_SECRET",
    "ANALYTICS_DB_PASSWORD",
    "ANALYTICS_MEXC_API_KEY",
    "ANALYTICS_MEXC_API_SECRET",
    "ANALYTICS_MEXC_FUTURES_API_KEY",
    "ANALYTICS_MEXC_FUTURES_API_SECRET",
    "ANALYTICS_ARCUS_ADDRESS",
)
