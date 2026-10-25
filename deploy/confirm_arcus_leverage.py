"""Ask the VM analytics API to apply Arcus leverage. Print status only."""

import json
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from deploy.envfile import read_env


def main() -> None:
    analytics_path = sys.argv[1]
    arcus_path = sys.argv[2]
    with open(analytics_path, encoding="utf-8") as handle:
        analytics = read_env(handle.read())
    try:
        with open(arcus_path, encoding="utf-8") as handle:
            arcus = read_env(handle.read())
    except FileNotFoundError:
        print("arcus env absent")
        return
    if not arcus.get("ARCUS_ADDRESS", "").strip() or not arcus.get("ARCUS_SIGNING_KEY", "").strip():
        print("arcus env absent")
        return
    secret = analytics.get("ANALYTICS_API_SECRET", "").strip()
    if not secret:
        print("arcus executor secret absent")
        return
    request = Request(
        "http://127.0.0.1:8080/api/arcus/leverage",
        data=b"{}",
        method="POST",
        headers={"Authorization": f"Bearer {secret}", "Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            status = response.status
            raw = response.read(500)
    except HTTPError as exc:
        status = exc.code
        raw = exc.read(500)
    detail = ""
    try:
        payload = json.loads(raw.decode("utf-8", "replace"))
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        detail = str(payload.get("detail") or payload.get("status") or "")
    print(f"{status} {detail}".strip())


if __name__ == "__main__":
    main()
