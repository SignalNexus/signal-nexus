import hmac
import os


def webhook_secret_matches(provided: str) -> bool:
    expected = os.environ.get("WEBHOOK_SECRET", "")
    if not expected:
        return False
    return hmac.compare_digest(provided, expected)


def portal_password_matches(provided: str) -> bool:
    expected = os.environ.get("PORTAL_PASSWORD", "")
    if not expected or not provided or len(provided) != len(expected):
        return False
    return hmac.compare_digest(provided, expected)


def analytics_secret_matches(provided: str) -> bool:
    expected = os.environ.get("ANALYTICS_API_SECRET", "")
    if not expected or not provided or len(provided) != len(expected):
        return False
    return hmac.compare_digest(provided, expected)
