"""Print whether the VM has MEXC order key names. Do not print values."""

import sys

from deploy.envfile import read_env


def main() -> None:
    path = sys.argv[1]
    try:
        with open(path, encoding="utf-8") as handle:
            values = read_env(handle.read())
    except FileNotFoundError:
        print("mexc spot keys absent")
        print("mexc futures keys absent")
        return
    spot = values.get("MEXC_API_KEY", "").strip() and values.get("MEXC_API_SECRET", "").strip()
    futures = values.get("MEXC_FUTURES_API_KEY", "").strip() and values.get("MEXC_FUTURES_API_SECRET", "").strip()
    print("mexc spot keys present" if spot else "mexc spot keys absent")
    print("mexc futures keys present" if futures else "mexc futures keys absent")


if __name__ == "__main__":
    main()
