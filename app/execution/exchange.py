import os


def mexc_client():
    api_key = os.environ.get("MEXC_API_KEY", "")
    secret = os.environ.get("MEXC_API_SECRET", "")
    if not api_key or not secret:
        raise RuntimeError("MEXC credentials are not configured")
    import ccxt

    return ccxt.mexc(
        {
            "apiKey": api_key,
            "secret": secret,
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        }
    )


def futures_client():
    api_key = os.environ.get("MEXC_FUTURES_API_KEY", "")
    secret = os.environ.get("MEXC_FUTURES_API_SECRET", "")
    if not api_key or not secret:
        raise RuntimeError("MEXC futures credentials are not configured")
    import ccxt

    from app.execution.positions import HISTORY_DAYS

    # since 付きの先物 fetch_orders は、この窓が無いと照会自体が失敗する。
    return ccxt.mexc(
        {
            "apiKey": api_key,
            "secret": secret,
            "enableRateLimit": True,
            "options": {
                "defaultType": "swap",
                "maxTimeTillEnd": HISTORY_DAYS * 24 * 60 * 60 * 1000,
            },
        }
    )
