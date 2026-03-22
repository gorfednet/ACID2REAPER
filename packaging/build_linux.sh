#!/usr/bin/env bash
# Build a Linux folder distribution (PyInstaller onedir) — ship as .tar.gz or AppImage.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Verifying CHANGELOG matches pyproject version"
python3 scripts/verify_changelog.py

echo "==> Installing package + PyInstaller"
python3 -m pip install --upgrade pip wheel
python3 -m pip install ".[pyinstaller]"

echo "==> Running PyInstaller"
rm -rf build dist
python3 -m PyInstaller packaging/pyinstaller.spec

OUT="${ROOT}/dist/ACID2Reaper"
if [[ ! -d "$OUT" ]]; then
  echo "Expected ${OUT} — check PyInstaller output."
  exit 1
fi

ARCHIVE="${ROOT}/dist/ACID2Reaper-linux-$(uname -m).tar.gz"
echo "==> Creating ${ARCHIVE}"
tar -C "${ROOT}/dist" -czvf "$ARCHIVE" ACID2Reaper
echo "Done: $ARCHIVE"
echo "Optional: use appimagetool on the unpacked tree for an AppImage."
