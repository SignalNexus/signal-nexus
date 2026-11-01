"""Make one Python environment and the venue directory match a resolved lock.

The caller supplies paths. This module does not know a host or a service manager.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def place(source: Path, dest: Path, import_names: list[str]) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    wanted = set(import_names)
    for child in dest.iterdir():
        if child.is_dir() and child.name not in wanted:
            shutil.rmtree(child)
    for name in import_names:
        target = dest / name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source / name, target, ignore=shutil.ignore_patterns(".git"))


def write_pth(venv_python: Path, dest: Path, import_names: list[str]) -> None:
    site = subprocess.check_output(
        [str(venv_python), "-c", "import site; print(site.getsitepackages()[0])"],
        text=True,
    ).strip()
    path = Path(site) / "venueadd.pth"
    lines = [str(dest / name) for name in import_names]
    path.write_text(("\n".join(lines) + "\n") if lines else "", encoding="utf-8")


def sync_lock(uv: str, venv_python: Path, lock: Path) -> None:
    no_deps_file = lock.with_suffix(".no-deps")
    no_deps = []
    if no_deps_file.is_file():
        no_deps = [line.strip() for line in no_deps_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    names = {pin.split("==", 1)[0].lower() for pin in no_deps}
    kept = [
        line
        for line in lock.read_text(encoding="utf-8").splitlines()
        if line.split("==", 1)[0].split("[", 1)[0].strip().lower() not in names
    ]
    filtered = lock.with_suffix(".sync")
    filtered.write_text("\n".join(kept) + "\n", encoding="utf-8")
    subprocess.run([uv, "pip", "sync", "--python", str(venv_python), str(filtered)], check=True)
    for pin in no_deps:
        subprocess.run(
            [uv, "pip", "install", "--python", str(venv_python), "--no-deps", pin],
            check=True,
        )


def main() -> None:
    if len(sys.argv) != 6:
        raise SystemExit("usage: apply.py SOURCE DEST VENV_PYTHON LOCK IMPORTS_FILE")
    source, dest, python, lock, imports = map(Path, sys.argv[1:])
    names = [line.strip() for line in imports.read_text(encoding="utf-8").splitlines() if line.strip()]
    place(source, dest, names)
    write_pth(python, dest, names)
    if names:
        sync_lock(os_uv(), python, lock)


def os_uv() -> str:
    found = shutil.which("uv")
    if not found:
        raise SystemExit("uv is not installed")
    return found


if __name__ == "__main__":
    main()
