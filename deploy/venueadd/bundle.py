"""Stage the checked-out venues and the import list for the orchestrator."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from deploy.venueadd.manifest import load_manifest


def stage(manifest: Path, checkout: Path, bundle: Path) -> None:
    rows = load_manifest(manifest) if manifest.is_file() else []
    bundle.mkdir(parents=True, exist_ok=True)
    trees = bundle / "trees"
    if trees.exists():
        shutil.rmtree(trees)
    trees.mkdir()
    for row in rows:
        shutil.copytree(
            checkout / row["import_name"],
            trees / row["import_name"],
            ignore=shutil.ignore_patterns(".git"),
        )
    names = [row["import_name"] for row in rows]
    (bundle / "imports.txt").write_text(("\n".join(names) + "\n") if names else "", encoding="utf-8")


def main() -> None:
    manifest = Path(sys.argv[1] if len(sys.argv) > 1 else "venueadd/venues.yaml")
    checkout = Path(sys.argv[2] if len(sys.argv) > 2 else "build/venueadd")
    bundle = Path(sys.argv[3] if len(sys.argv) > 3 else "build/venueadd-out")
    stage(manifest, checkout, bundle)


if __name__ == "__main__":
    main()
