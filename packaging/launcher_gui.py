"""
PyInstaller bootstrap for the windowed GUI (see packaging/pyinstaller.spec).

Keeping this tiny avoids dragging PyInstaller hooks into the main package.
"""

from __future__ import annotations

if __name__ == "__main__":
    from acid2reaper.ui.desktop import run_app

    raise SystemExit(run_app())
