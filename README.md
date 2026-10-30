# ACID2Reaper

**Beta, version 0.2.** ACID2Reaper converts **Sonic Foundry / Sony / MAGIX ACID** projects (`.acd`, `.acd-bak`, `.acd-zip`) to **Cockos REAPER** `.rpp` projects.

[![CI](https://github.com/gorfednet/ACID2REAPER/actions/workflows/ci.yml/badge.svg)](https://github.com/gorfednet/ACID2REAPER/actions/workflows/ci.yml)
[![License: CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg)](LICENSE)

## Features

- A **command-line** tool and an optional **graphical** window (Tkinter, on macOS, Windows and Linux).
- **Structural timeline parsing** for the GUID-chunked Wave64 ACID layout across
  several ACID build generations. Other variants get a cautious fingerprint and
  heuristic read.
- **Tempo, time signature and beat mapping** decoded from the project's own
  timebase record. One-shots stay unstretched.
- **Safety limits** on file and ZIP sizes, path validation, and sanitized paths in the exported RPP.
- **PyInstaller** recipes for **macOS** (`.app` / `.dmg`), **Windows** (folder + `ACID2Reaper.exe`), and **Linux** (tarball).

ACID2Reaper can't guarantee 100% parity with ACID, so open the result in REAPER and check the tempo, stretch, media and automation.

For the Sony Wave64-style ACID layout, ACID2Reaper reads the project tempo, PPQ
and time signature from the project's timebase record, and emits each event at
its decoded timeline position and length. It also reads the per-track cached
source loop `acid` chunk and exports its tempo as a REAPER `PLAYRATE` (pitch
preserved). A loop authored at a different tempo than the project is therefore
beat-mapped instead of played at its raw speed; one-shots are left alone.
Container variants that aren't catalogued still fall back to neutral media
references at `0:00`.

ACID2Reaper writes its diagnostics (decoded tempo and meter, sources left
unstretched, media it couldn't find) into the project's REAPER `NOTES` block,
and prints them to stderr with `-v`.

## Format coverage and known limitations

The GUID chunk roles and byte offsets are catalogued in
[`src/acid2reaper/data/acd_signatures.json`](src/acid2reaper/data/acd_signatures.json)
under `wave64_layout`, which marks each chunk as decoded or undecoded.

Decoding is validated three ways. One is byte-level agreement with a real ACID 3-era
project. Another is a structural corpus of 245 real projects spanning roughly 2005–2008 and
thirty distinct build layouts (`tests/fixtures/corpus_manifest.json`, which holds structural
fingerprints only, with no audio or file names). The third is synthetic fixtures for the
meters, layouts and edge cases that no real sample covered.

What is **verified**:

- **Tempo.** Read from the project's timebase record as microseconds per beat.
  Corroborated against rendered mixdowns: one corpus project has three separate
  renders, all 293.9 s over a timeline of exactly 480 beats, which is 98.00 BPM,
  and the record decodes to exactly that.
- **Time signature.** A `uint16` pair, in the timebase record where present and
  the project record otherwise. For 3/4, 5/4, 6/8, 7/8 and 12/8 only one half
  can legally be a denominator, so the pair resolves itself.
- **Multi-track projects, across builds.** Older builds store a track's media
  path in the track record; newer builds use a dedicated leaf. Both are read,
  so projects saved by different ACID versions now convert alike.
- **One-shots.** The cached `acid` chunk's flag word is decoded, and sources
  flagged as one-shots are never stretched.

What remains **unverified or unsupported**:

- **Which note the tempo counts under x/8 meters.** Every project available is
  in x/4, where quarter-note BPM and beat-unit BPM are identical. The assumption
  is isolated in `acid_timing.seconds_per_tick` and pinned by the 6/8 and 12/8
  golden files, so a real x/8 project would show up as a visible diff.
- **Ambiguous meter pairs.** When both halves are powers of two (4/4, 4/8) the
  slot order cannot be inferred. The default follows the documented `acid` chunk
  convention; `--time-sig-order` and `--time-sig` override it.
- **Tempo and meter changes.** Only one timebase record has ever been observed
  per project, so a mid-project change would be flattened.
- **Stretch markers, envelopes, automation, clip gain, pan, pitch and fades.**
  Catalogued where seen, but not interpreted, and never invented.
- **MP3, OGG and FLAC clip lengths.** `media_duration` uses the standard library,
  which covers WAV and AIFF only; other formats fall back to a default length
  when the project does not supply one.

If you have `.acd` files that exercise the unverified cases, especially a
genuine x/8 project, please attach them to an issue.

## Requirements

- **Python 3.9+**
- Pip package dependencies: see `pyproject.toml` (includes `rpp`).

## Install

### From a GitHub Release (recommended)

```bash
python3 -m pip install \
  https://github.com/gorfednet/ACID2REAPER/releases/download/v0.2.0/acid2reaper-0.2.0-py3-none-any.whl
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
# Convert; the output is written next to the input unless you pass an output path
acid2reaper path/to/project.acd

# The output path is positional; --media-dir may be repeated
acid2reaper path/to/bundle.acd-zip out.rpp --media-dir /path/to/audio

# Show what was decoded (tempo, meter, unstretched sources, missing media)
acid2reaper path/to/project.acd -v

# Override the time signature when a project converts with the wrong one
acid2reaper path/to/project.acd --time-sig 6/8
acid2reaper path/to/project.acd --time-sig-order num-den

# Graphical UI
acid2reaper --gui
# or: acid2reaper-gui
```

## Version

- **Package version:** `0.2.0` (see `src/acid2reaper/_version.py`). It's distributed through **GitHub Releases**; PyPI may follow.
- **Marketing label:** **0.2 (Beta)**.

```bash
acid2reaper --version
```

## Testing

```bash
python -m pytest -q
```

Three suites are opt-in and skipped by default:

```bash
# Convert a local folder of real ACID projects end to end
ACID2REAPER_CORPUS_DIR=~/Music python -m pytest -m corpus -q

# Check generated projects against a local REAPER install (attended:
# an unlicensed REAPER shows an evaluation nag that needs dismissing)
ACID2REAPER_REAPER_ORACLE=1 python -m pytest -m reaper -q

# Regenerate the golden REAPER projects after an intended output change
python scripts/update_goldens.py
python scripts/update_goldens.py --check   # CI uses this
```

## Building binaries

See [packaging/BUILD.md](packaging/BUILD.md). For **git tag names** and automated **GitHub Releases** (sdist and wheel on tag push), see [RELEASING.md](RELEASING.md). Every release build must pass:

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

[Creative Commons Attribution 4.0 International (CC BY 4.0)](LICENSE). You may use, share and build on this work (including in modified form) if you **give appropriate credit**, link to the licence and **indicate changes** where applicable. See Section 3(a) of the licence text.

## Trademarks

*ACID* is a trademark of its respective owners. *REAPER* is a trademark of Cockos Incorporated. This project is not affiliated with or endorsed by MAGIX, Sony, Sonic Foundry, or Cockos.
