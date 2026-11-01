"""Confirm purchased packages with the production venue loader."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from deploy.venueadd.manifest import load_manifest


def validate(import_names: list[str], venue_ids: list[str], pythonpath: list[str]) -> None:
    from app.execution.venue_port import VenuePortError, clear_ports, load_ports

    previous = os.environ.get("SIGNAL_NEXUS_VENUEADD")
    path = sys.path[:]
    sys.path[:0] = pythonpath
    os.environ["SIGNAL_NEXUS_VENUEADD"] = ",".join(import_names)
    try:
        clear_ports()
        loaded = load_ports()
    except VenuePortError as exc:
        raise SystemExit(str(exc)) from exc
    finally:
        clear_ports()
        sys.path[:] = path
        if previous is None:
            os.environ.pop("SIGNAL_NEXUS_VENUEADD", None)
        else:
            os.environ["SIGNAL_NEXUS_VENUEADD"] = previous
    found = set(loaded)
    expected = set(venue_ids)
    if found != expected:
        raise SystemExit(f"loaded venues {sorted(found)} != {sorted(expected)}")


def main() -> None:
    manifest = Path(sys.argv[1] if len(sys.argv) > 1 else "venueadd/venues.yaml")
    checkout = Path(sys.argv[2] if len(sys.argv) > 2 else "build/venueadd")
    rows = load_manifest(manifest)
    if not rows:
        return
    validate(
        [row["import_name"] for row in rows],
        [row["venue_id"] for row in rows],
        [str(checkout / row["import_name"]) for row in rows],
    )


if __name__ == "__main__":
    main()
