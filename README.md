# ACID2Reaper

**First public beta — version 0.1.** Convert **Sonic Foundry / Sony / MAGIX ACID** projects (`.acd`, `.acd-bak`, `.acd-zip`) to **Cockos REAPER** `.rpp` projects.

[![CI](https://github.com/gorfednet/ACID2Reaper/actions/workflows/ci.yml/badge.svg)](https://github.com/gorfednet/ACID2Reaper/actions/workflows/ci.yml)
[![License: CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg)](LICENSE)

## Features

- **CLI** and optional **graphical** interface (Tkinter, cross-platform).
- **Heuristic parsing** of proprietary ACID binaries, plus **fingerprinted** layouts where catalogued.
- **Safety limits** on file and ZIP sizes, path validation, and sanitized paths in exported RPP.
- **PyInstaller** recipes for **macOS** (`.app` / `.dmg`), **Windows** (folder + `ACID2Reaper.exe`), and **Linux** (tarball).

Parsing cannot guarantee 100% parity with ACID; always open the result in REAPER and verify tempo, media, and automation.

## Requirements

- **Python 3.9+**
- Pip package dependencies: see `pyproject.toml` (includes `rpp`).

## Install (from source)

```bash
git clone https://github.com/gorfednet/ACID2Reaper.git
cd ACID2Reaper
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install .
```

Optional: `pip install ".[ole]"` for OLE compound project support where applicable.

## Usage

```bash
# Convert; writes alongside the input unless you pass an output path
acid2reaper path/to/project.acd

acid2reaper path/to/bundle.acd-zip -o out.rpp --media-dir /path/to/audio

# Graphical UI
acid2reaper --gui
# or: acid2reaper-gui
```

## Version

- **PyPI / package version:** `0.1.0` (see `src/acid2reaper/_version.py`).
- **Marketing label:** **0.1 (Beta)**.

```bash
acid2reaper --version
```

## Building binaries

See [packaging/BUILD.md](packaging/BUILD.md). For **git tag names**, **PyPI**, and automated **GitHub Releases** (sdist/wheel on tag push), see [RELEASING.md](RELEASING.md). Every release build should pass:

```bash
python scripts/verify_changelog.py
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Security

See [SECURITY.md](SECURITY.md).

## License

[Creative Commons Attribution 4.0 International (CC BY 4.0)](LICENSE). You may use, share, and build on this work (including in modified form) if you **give appropriate credit**, link to the license, and **indicate changes** where applicable—see Section 3(a) of the license text.

## Trademarks

*ACID* is a trademark of its respective owners. *REAPER* is a trademark of Cockos Incorporated. This project is not affiliated with or endorsed by MAGIX, Sony, Sonic Foundry, or Cockos.
