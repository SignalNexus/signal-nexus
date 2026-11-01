#!/bin/bash
# Replace the live strategies file only after the staged file matches and loads.
# A rejected staged file is removed. The live file stays in place.
set -euo pipefail

ROOT="${1:?CORE_DIRECTORY is required}"
EXPECTED="${2:?sha256 is required}"
NEW="$ROOT/config/strategies.yml.new"
LIVE="$ROOT/config/strategies.yml"
PREV="$ROOT/config/strategies.yml.prev"

reject() {
  rm -f "$NEW"
  echo "$1" >&2
  exit 1
}

if [[ ! -s "$NEW" ]]; then
  reject "strategies.yml.new is missing"
fi
actual="$(sha256sum "$NEW" | awk '{print $1}')"
if [[ "$actual" != "$EXPECTED" ]]; then
  reject "strategies.yml.new sha256 ${actual} != ${EXPECTED}"
fi
if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  reject "analytics virtualenv is missing"
fi
if ! (
  cd "$ROOT"
  .venv/bin/python - "$NEW" <<'PY'
import sys
from pathlib import Path
from app.execution.router import load_strategies

if not load_strategies(Path(sys.argv[1])):
    raise SystemExit(1)
PY
); then
  reject "strategies.yml.new rejected"
fi
echo "strategies.yml loaded"
if [[ ! -s "$LIVE" ]]; then
  reject "strategies.yml is missing on the VM"
fi
cp -a "$LIVE" "$PREV"
mv -f "$NEW" "$LIVE"
echo "strategies.yml sha256 ${actual}"
