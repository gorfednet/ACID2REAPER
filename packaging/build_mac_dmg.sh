#!/usr/bin/env bash
# Build a macOS .app (PyInstaller) and wrap it in a compressed .dmg disk image.
# Run from the project root on a Mac with Python 3.9+.
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

APP="${ROOT}/dist/ACID2Reaper.app"
if [[ ! -d "$APP" ]]; then
  echo "Expected ${APP} — check PyInstaller output above."
  exit 1
fi

DMG="${ROOT}/dist/ACID2Reaper-macos.dmg"
echo "==> Creating ${DMG}"
rm -f "$DMG"
hdiutil create -volname "ACID2Reaper" -srcfolder "$APP" -ov -format UDZO "$DMG"
echo "Done: $DMG"
