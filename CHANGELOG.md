# Changelog

All notable changes to **ACID2Reaper** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Release builds run `python scripts/verify_changelog.py` so every published version
must have a matching section below.

## [0.1.3] - 2026-08-28

Patch release with a user-visible timeline change: clips are now time-stretched to
the project tempo instead of always exporting at their raw speed.

### Added

- Parsing for the per-track `5c538752-e345-4f78-83b8-551935b4c6f7` chunk in the
  catalogued Wave64 ACID layout. Its payload holds a verbatim copy of the source
  media file's standard ACID `acid` RIFF chunk, which caches that source's own
  loop tempo and beat count.
- `wave64_layout` section in `data/acd_signatures.json` cataloguing container and
  chunk roles for all 29 GUIDs observed in the fixture, with decoded byte offsets
  and explicit `unverified_fields` entries. No GUIDs are synthesized.
- README "Format coverage and known limitations" section.

### Changed

- Clips now export a REAPER `PLAYRATE` of `project_tempo / source_tempo` with
  pitch preserved, so a loop authored at a different tempo than the project is
  beat-mapped rather than played at its raw speed. For the ACID 3 fixture this is
  `120 / 139.557 = 0.85986`. Projects whose sources match the project tempo are
  unaffected.
- Playrate is clamped on export: non-finite, zero, negative, or out-of-range
  (outside 0.01–100) values fall back to `1.0` and no `PLAYRATE` line is written.

### Notes

- Everything decoded here comes from **one** real project file, so non-4/4
  time-signature field order and multi-track layouts remain **unverified**. The
  project record's time signature is a `uint16` pair whose numerator/denominator
  order cannot be determined from a 4/4-only sample; the parser still falls back
  to 4/4 rather than guessing.
- The cached `acid` chunk's flag word (which marks one-shots in the standard
  chunk) is `0` in the only sample, so no flag meaning is inferred and one-shot
  sources are not excluded from stretching.

## [0.1.2] - 2026-08-28

Patch release: media lookup is anchored to the source project and reports missing
files; the CLI documentation reflects its positional output argument; the GUI can
select an extra media folder; ZIP traversal and uncompressed-size limits have
regression coverage; dependencies, CI, packaging assets, and release preflight are
hardened. The catalogued GUID-chunked Wave64 ACID layout now exports real event
positions and lengths using decoded tempo and PPQ fields. Unverified record values
are no longer interpreted as clip pitch or volume.

## [0.1.1] - 2026-03-22

Patch release: shared UTF-16LE string scanning (`string_scan`) used by `scan`, `acid_timeline`, and `acid_routing`; REAPER float formatting centralized in `rpp_format`; GUI uses grouped `LabelFrame` layout, clearer status wording, and theme foreground for status (no hard-coded hex colors). Tests added for string scan and float formatting.

## [0.1.0] - 2026-03-22

First public **Beta** release of **ACID2Reaper** (`acid2reaper` **0.1.0**): CLI and Tk desktop conversion from ACID (`.acd`, `.acd-bak`, `.acd-zip`) to Cockos REAPER (`.rpp`), heuristic and fingerprinted parsing, security limits on project and ZIP handling, PyInstaller bundles for macOS (`.app` / `.dmg`), Windows (folder + `ACID2Reaper-windows.zip`), and Linux (tarball), GitHub CI plus tag-based wheel/sdist and release automation, project documentation, and **CC BY 4.0** licensing.
