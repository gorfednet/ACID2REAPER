#!/usr/bin/env python3
"""
Ensure CHANGELOG.md documents the current release in pyproject.toml / _version.py.

Run before PyInstaller builds and in CI so releases never ship without notes.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def read_pyproject_version(root: Path) -> str:
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not m:
        print("verify_changelog: could not find version in pyproject.toml", file=sys.stderr)
        sys.exit(1)
    return m.group(1)


def read_package_version(root: Path) -> str:
    text = (root / "src" / "acid2reaper" / "_version.py").read_text(encoding="utf-8")
    m = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not m:
        print("verify_changelog: could not find __version__ in _version.py", file=sys.stderr)
        sys.exit(1)
    return m.group(1)


def main() -> int:
    root = _project_root()
    ver = read_pyproject_version(root)

    # The version is duplicated in two files. Only pyproject was ever checked,
    # so a stale _version.py would ship a wheel that reports the wrong version
    # from --version and from the packaged GUI.
    package_ver = read_package_version(root)
    if package_ver != ver:
        print(
            f"verify_changelog: version mismatch -- pyproject.toml says {ver}, "
            f"src/acid2reaper/_version.py says {package_ver}.",
            file=sys.stderr,
        )
        return 1

    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    # Keep a Changelog style: ## [0.1.0]
    if f"## [{ver}]" not in changelog:
        print(
            f"verify_changelog: CHANGELOG.md must contain a section '## [{ver}]' "
            f"(current pyproject version is {ver}).",
            file=sys.stderr,
        )
        return 1
    print(f"verify_changelog: OK (version {ver} consistent, CHANGELOG documents [{ver}])")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
