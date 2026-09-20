# Changelog

All notable changes to **ACID2Reaper** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Release builds run `python scripts/verify_changelog.py` so every published version
must have a matching section below.

## [0.2.0] - 2026-09-20

Conversion correctness release. Running the converter over 245 real ACID projects
spanning roughly 2005-2008 and thirty distinct build layouts exposed defects that
a single 4/4, 120 BPM fixture could not. Output changes for essentially every
project, so re-convert anything you converted with an earlier version.

### Fixed

- **Project tempo was read from the wrong field.** The float64 in the project
  record is a template default: it reads exactly 120.0 in all 245 real projects
  examined, including ones authored at 98, 145, 178 and 184 BPM. Every
  conversion therefore emitted `TEMPO 120`, and because clip playrate is
  `project_tempo / source_tempo`, stretched every clip by the wrong factor onto a
  wrong bar grid. The tempo is now read from the `946739be` timebase record as
  microseconds per beat. Corroborated against rendered mixdowns: one project has
  three separate renders, all 293.9 s over exactly 480.0 beats, which is 98.00
  BPM, and the record decodes to exactly that.
- **Time signature was unreachable.** It was read as two uint32 candidates that
  for a 4/4 project are 0 and 262148, both outside the plausibility gate, so
  every project silently fell back to 4/4 regardless of its meter. It is a
  uint16 pair.
- **Media paths failed on newer ACID builds.** Those builds leave the track
  record empty and put the path in a dedicated `bf0a0344` leaf, so 31 of 244
  projects resolved zero paths and every one of their tracks collapsed onto a
  single fallback file. Both layouts are now read; no project in the corpus
  resolves zero paths.
- **Event positions were read as unsigned.** ACID stores them signed, and allows
  an event to sit left of bar 1; read as uint64, a position of -41026 ticks
  became 1.8e19 and placed the clip about ten million years into the project.
  Such clips are now trimmed into the take's source offset, or dropped and
  reported if they lie entirely before the start.
- **One-shots were stretched.** The `acid` chunk's flag word was never decoded,
  so every source with a plausible cached tempo was resampled to the project
  tempo -- which audibly retunes a hit. 97 of the 245 corpus projects contain a
  one-shot source.
- **Scientific notation could reach the output.** `format_rpp_float` used `%g`,
  which emits `3.1059307775e+14` for extreme values; REAPER's chunk parser reads
  plain decimals and misreads that silently.
- **Windows absolute paths were joined onto the project directory**, producing
  `FILE` tokens such as `/home/me/project/C:\audio\loop.wav`.
- **Tracks with no events were dropped**, renumbering every track after the gap
  and making an otherwise-valid empty project decode to nothing.
- **A root size left at the bare header length rejected the whole file.** The
  chunk stream is intact in that case, so the file extent is used instead.
- **`media_duration` broke the CLI on Python 3.13.** It imported `aifc` at module
  scope; `aifc` was removed in 3.13 (PEP 594), so importing the module -- and
  with it the whole CLI -- raised `ImportError`.

### Added

- `--time-sig NUM/DEN` and `--time-sig-order {den-num,num-den}` to override meter
  decoding, for the pairs where both halves are powers of two and the slot order
  cannot be inferred.
- Project diagnostics are written to a REAPER `NOTES` block and printed to stderr
  with `-v`. They were fully computed before and went nowhere.
- Items carry a `NAME`, so a project reusing one loop across several tracks is
  readable in the arrange view.
- `binary/acid_chunk.py`, a shared decoder and encoder for the standard `acid`
  RIFF chunk, and `binary/meter.py` for time-signature pair resolution.
- `acid_timing.seconds_per_tick`, isolating the unverified assumption that ACID's
  BPM counts quarter notes under x/8 meters.
- Test infrastructure: an ACID project and ACIDized WAV builder anchored to the
  real fixture by byte equality, a structural `.rpp` validator, fifteen golden
  projects covering 3/4, 5/4, 6/8, 7/8, 12/8, one-shots, multi-track and both
  media layouts, a committed structural corpus manifest for 245 real projects,
  an opt-in live corpus runner, and an opt-in REAPER oracle.
- Python 3.13 in the CI matrix; coverage and lint jobs.

### Changed

- Documentation now distinguishes what is verified from what is not, backed by
  the corpus rather than by a single sample.

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
