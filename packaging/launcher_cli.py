"""
PyInstaller bootstrap for the console CLI (see packaging/pyinstaller.spec).
"""

from __future__ import annotations

if __name__ == "__main__":
    from acid2reaper.cli import main

    raise SystemExit(main())
