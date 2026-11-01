"""Resolve Core and purchased VenueAdd requirements into one lock."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from deploy.venueadd.exceptions import load_exceptions, split_requirements
from deploy.venueadd.manifest import load_manifest

_CONSTRAINTS = Path(__file__).with_name("constraints.txt")


def assemble(core: str, venues: list[str], exceptions: list[dict[str, object]]) -> tuple[str, list[str]]:
    parts = [core]
    pins: list[str] = []
    for text in venues:
        kept, extra = split_requirements(text, exceptions)
        parts.append(kept)
        pins.extend(extra)
    return "\n".join(parts), pins


def compile_lock(core: Path, requirement_files: list[Path], output: Path, uv: str = "uv") -> None:
    exceptions = load_exceptions()
    texts = [path.read_text(encoding="utf-8") if path.is_file() else "" for path in requirement_files]
    combined, pins = assemble(core.read_text(encoding="utf-8"), texts, exceptions)
    for pin in pins:
        combined += "\n" + "\n".join(dependency_lines(uv, pin, exceptions)) + "\n"
    work = output.parent
    work.mkdir(parents=True, exist_ok=True)
    requirements = work / "resolved-input.txt"
    requirements.write_text(combined, encoding="utf-8")
    compiled = work / "compiled.txt"
    subprocess.run(
        [
            uv,
            "pip",
            "compile",
            str(requirements),
            "--constraint",
            str(_CONSTRAINTS),
            "--python-version",
            "3.12",
            "--output-file",
            str(compiled),
        ],
        check=True,
    )
    lines = compiled.read_text(encoding="utf-8").splitlines()
    have = {_name(line) for line in lines}
    for pin in pins:
        if _name(pin) not in have:
            lines.append(pin)
    if "urllib3" not in have:
        lines.append("urllib3==2.8.0")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    no_deps = output.with_suffix(".no-deps")
    no_deps.write_text(("\n".join(pins) + "\n") if pins else "", encoding="utf-8")


def requirement_files(manifest: Path, checkout: Path) -> list[Path]:
    return [
        checkout / row["import_name"] / row["requirements_file"]
        for row in load_manifest(manifest)
    ]


def dependency_lines(uv: str, pin: str, exceptions: list[dict[str, object]]) -> list[str]:
    dropped = {
        name.lower()
        for item in exceptions
        if f"{item.get('distribution')}=={item.get('version')}" == pin
        for name in item.get("drop_requires") or []
    }
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "in.txt"
        output = Path(directory) / "out.txt"
        source.write_text(pin + "\n", encoding="utf-8")
        subprocess.run(
            [uv, "pip", "compile", str(source), "--python-version", "3.12", "--output-file", str(output)],
            check=True,
        )
        lines = []
        for raw in output.read_text(encoding="utf-8").splitlines():
            if not raw.strip() or raw.startswith("#") or raw.startswith("-"):
                continue
            name = _name(raw)
            if name in dropped or name == _name(pin):
                continue
            lines.append(raw.strip())
        return lines


def _name(line: str) -> str:
    return line.split("==", 1)[0].split("[", 1)[0].strip().lower()


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("usage: resolve.py CORE_REQUIREMENTS VENUE_CHECKOUT LOCK_FILE")
    core, checkout, output = (Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
    manifest = Path(os.environ.get("VENUES_MANIFEST", "venueadd/venues.yaml"))
    compile_lock(core, requirement_files(manifest, checkout), output)


if __name__ == "__main__":
    main()
