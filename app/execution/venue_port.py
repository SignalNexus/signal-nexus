import importlib
import logging
import os

logger = logging.getLogger(__name__)

SUPPORTED_PORT_VERSION = 1
RESERVED_VENUE_IDS = frozenset({"arcus", "mexc_spot", "mexc_futures"})
_METHODS = ("execute", "mark", "sync_lots", "open_orders", "balance", "apply_leverage")
_ports: dict[str, object] | None = None


class VenuePortError(RuntimeError):
    pass


def clear_ports() -> None:
    global _ports
    _ports = None


def load_ports() -> dict[str, object]:
    global _ports
    names = [part.strip() for part in os.environ.get("SIGNAL_NEXUS_VENUEADD", "").split(",") if part.strip()]
    loaded: dict[str, object] = {}
    for name in names:
        port = _load_one(name)
        venue_id = port.venue_id
        if venue_id in RESERVED_VENUE_IDS:
            logger.error("reserved venue id %s from %s", venue_id, name)
            raise VenuePortError(f"reserved venue id: {venue_id}")
        if venue_id in loaded:
            logger.error("duplicate venue id %s", venue_id)
            raise VenuePortError(f"duplicate venue id: {venue_id}")
        loaded[venue_id] = port
    _ports = loaded
    return loaded


def ports() -> dict[str, object]:
    if _ports is None:
        return load_ports()
    return _ports


def port_for(venue_id: str):
    return ports().get(venue_id)


def _load_one(name: str):
    try:
        module = importlib.import_module(name)
    except Exception as exc:
        logger.error("venueadd import failed: %s", name)
        raise VenuePortError(f"venueadd import failed: {name}") from exc
    if getattr(module, "PORT_VERSION", None) != SUPPORTED_PORT_VERSION:
        logger.error("venueadd port version mismatch: %s", name)
        raise VenuePortError(f"venueadd port version mismatch: {name}")
    try:
        port = module.port()
    except Exception as exc:
        logger.error("venueadd port() failed: %s", name)
        raise VenuePortError(f"venueadd port() failed: {name}") from exc
    if getattr(port, "version", SUPPORTED_PORT_VERSION) != SUPPORTED_PORT_VERSION:
        logger.error("venueadd port version mismatch: %s", name)
        raise VenuePortError(f"venueadd port version mismatch: {name}")
    venue_id = getattr(port, "venue_id", None)
    if not isinstance(venue_id, str) or not venue_id:
        logger.error("venueadd port has no venue id: %s", name)
        raise VenuePortError(f"venueadd port has no venue id: {name}")
    missing = [method for method in _METHODS if not callable(getattr(port, method, None))]
    if missing:
        logger.error("venueadd port missing %s: %s", ", ".join(missing), name)
        raise VenuePortError(f"venueadd port missing {missing[0]}: {name}")
    return port
