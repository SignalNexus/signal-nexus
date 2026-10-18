import os
import sys
from pathlib import Path

from deploy.envfile import read_env


def confirm_futures_read() -> None:
    api_key = os.environ.get("ANALYTICS_MEXC_FUTURES_API_KEY", "")
    secret = os.environ.get("ANALYTICS_MEXC_FUTURES_API_SECRET", "")
    if not api_key or not secret:
        raise RuntimeError("futures read credentials are not configured")
    import ccxt

    exchange = ccxt.mexc(
        {
            "apiKey": api_key,
            "secret": secret,
            "enableRateLimit": True,
            "options": {"defaultType": "swap"},
        }
    )
    try:
        trades = exchange.fetch_my_trades("ETH/USDT:USDT", limit=1)
    except Exception as exc:
        text = str(exc)
        if api_key in text or secret in text:
            raise RuntimeError("futures read failed") from None
        raise RuntimeError(text[:300]) from None
    if not isinstance(trades, list):
        raise RuntimeError("futures trades are unavailable")


def main() -> None:
    values = read_env(Path(sys.argv[1]).read_text(encoding="utf-8"))
    os.environ["ANALYTICS_MEXC_FUTURES_API_KEY"] = values.get("ANALYTICS_MEXC_FUTURES_API_KEY", "")
    os.environ["ANALYTICS_MEXC_FUTURES_API_SECRET"] = values.get("ANALYTICS_MEXC_FUTURES_API_SECRET", "")
    confirm_futures_read()
    print("futures read ok")


if __name__ == "__main__":
    main()
