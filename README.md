# ACID2Reaper

**First public beta — version 0.1.** Convert **Sonic Foundry / Sony / MAGIX ACID** projects (`.acd`, `.acd-bak`, `.acd-zip`) to **Cockos REAPER** `.rpp` projects.

[![CI](https://github.com/gorfednet/ACID2REAPER/actions/workflows/ci.yml/badge.svg)](https://github.com/gorfednet/ACID2REAPER/actions/workflows/ci.yml)
[![License: CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg)](LICENSE)

## Features

- **CLI** and optional **graphical** interface (Tkinter, cross-platform).
- **Structural timeline parsing** for the catalogued GUID-chunked Wave64 ACID
  layout, plus conservative fingerprint/heuristic handling of other variants.
- **Safety limits** on file and ZIP sizes, path validation, and sanitized paths in exported RPP.
- **PyInstaller** recipes for **macOS** (`.app` / `.dmg`), **Windows** (folder + `ACID2Reaper.exe`), and **Linux** (tarball).

Parsing cannot guarantee 100% parity with ACID; always open the result in REAPER and verify tempo, stretch, media, and automation.

For the catalogued Sony Wave64-style ACID layout, the converter reads project
tempo/PPQ and emits each event at its decoded timeline position and length. It
also reads the per-track cached source loop tempo and exports it as a REAPER
`PLAYRATE` (pitch preserved), so loops authored at a different tempo than the
project are beat-mapped instead of playing at their raw speed. Uncatalogued
container variants still fall back to neutral media references at `0:00`.

## Format coverage and known limitations

Everything decoded here was derived from **one** real project file
(`tests/fixtures/DrumRollUpDemo.acd`, a Sonic Foundry ACID 3-era demo). The GUID
chunk roles and byte offsets are catalogued in
[`src/acid2reaper/data/acd_signatures.json`](src/acid2reaper/data/acd_signatures.json)
under `wave64_layout`, which marks each chunk as decoded or undecoded.

Because the sample size is one, the following are **unverified** and must not be
assumed correct:

- **Non-4/4 time signatures.** The project record stores the signature as a
  `uint16` pair, but both halves are `4` in the only sample, so the
  numerator/denominator **field order is undetermined**. The parser gates these
  fields on a plausibility check and falls back to 4/4 rather than guessing, so a
  genuine 3/4 or 6/8 project may be exported as 4/4.
- **Multi-track projects.** The fixture has a single track with a single media
  source. Track ordering, per-track mixer state, and how multiple sources are
  associated with one track are inferred from a one-track layout only.
- **One-shot sources.** The cached source `acid` chunk has a flag word that in
  the standard chunk marks one-shots (which should not be stretched). It is `0`
  in the only sample, so no flag meaning is inferred and every source with a
  plausible cached tempo is beat-mapped. A one-shot could therefore receive a
  `PLAYRATE` it should not have.
- **Stretch markers, envelopes, and automation.** Cached `strc` slice data and
  the repeated 16-byte per-track records are catalogued but not interpreted.

Clip gain, pan, pitch, fades, and automation are likewise not invented from
undecoded fields.

If you have `.acd` files that exercise these cases — especially non-4/4 or
multi-track projects — please attach them to an issue so the layout can be
confirmed against more than one sample.

## Requirements

- **Python 3.9+**
- Pip package dependencies: see `pyproject.toml` (includes `rpp`).

## Install

### From a GitHub Release (recommended)

```bash
python3 -m pip install \
  https://github.com/gorfednet/ACID2REAPER/releases/download/v0.1.3/acid2reaper-0.1.3-py3-none-any.whl
```

On macOS, user installs often land in `~/Library/Python/3.9/bin` — put that directory on your `PATH`, or run `python3 -m acid2reaper`.

### From source

```bash
git clone https://github.com/gorfednet/ACID2REAPER.git
cd ACID2Reaper
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
python3 -m pip install -e .
```

Optional: `python3 -m pip install ".[ole]"` for OLE compound project support where applicable.

## Usage

```bash
# Convert; writes alongside the input unless you pass an output path
acid2reaper path/to/project.acd

# The output path is positional; --media-dir may be repeated
acid2reaper path/to/bundle.acd-zip out.rpp --media-dir /path/to/audio

# Graphical UI
acid2reaper --gui
# or: acid2reaper-gui
```

## Version

- **Package version:** `0.1.3` (see `src/acid2reaper/_version.py`). Distributed via **GitHub Releases** (PyPI optional later).
- **Marketing label:** **0.1 (Beta)**.

```bash
acid2reaper --version
```

## Building binaries

See [packaging/BUILD.md](packaging/BUILD.md). For **git tag names** and automated **GitHub Releases** (sdist/wheel on tag push), see [RELEASING.md](RELEASING.md). Every release build should pass:

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
