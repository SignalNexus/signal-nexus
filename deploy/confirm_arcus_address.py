"""Confirm the VM env has an Arcus address. Print the name only."""

import sys

from deploy.envfile import read_env


def main() -> None:
    path = sys.argv[1]
    with open(path, encoding="utf-8") as handle:
        values = read_env(handle.read())
    if not values.get("ANALYTICS_ARCUS_ADDRESS", "").strip():
        print("address name missing", file=sys.stderr)
        sys.exit(1)
    print("address name present")


if __name__ == "__main__":
    main()
