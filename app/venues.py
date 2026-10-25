from dataclasses import dataclass
from pathlib import Path

import yaml

from app.config_dir import config_file

REGISTRY_PATH = config_file("venues.yml")


@dataclass(frozen=True)
class Venue:
    id: str
    asset_class: str
    enabled: bool


def load_venues(path: Path | None = None) -> dict[str, Venue]:
    if path is None:
        path = REGISTRY_PATH
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    rows = loaded.get("venues") if isinstance(loaded, dict) else None
    if not isinstance(rows, list):
        raise ValueError("venue registry is invalid")
    venues: dict[str, Venue] = {}
    for raw in rows:
        if not isinstance(raw, dict):
            raise ValueError("venue registry is invalid")
        venue_id = raw.get("id")
        asset_class = raw.get("asset_class")
        enabled = raw.get("enabled")
        if (
            not isinstance(venue_id, str)
            or not venue_id
            or venue_id in venues
            or asset_class not in ("spot", "futures")
            or not isinstance(enabled, bool)
        ):
            raise ValueError("venue registry is invalid")
        venues[venue_id] = Venue(venue_id, asset_class, enabled)
    return venues


def asset_class_of(venue: str | None) -> str:
    if venue in (None, ""):
        venue = "mexc_spot"
    found = load_venues().get(venue)
    if found is None:
        return "unknown"
    return found.asset_class


def is_spot(venue: str | None) -> bool:
    return asset_class_of(venue) == "spot"


def is_futures(venue: str | None) -> bool:
    return asset_class_of(venue) == "futures"


def quote_currency(venue: str | None) -> str:
    if venue == "arcus":
        return "USD"
    return "USDT"


def enabled_venues() -> dict[str, Venue]:
    return {venue_id: venue for venue_id, venue in load_venues().items() if venue.enabled}
