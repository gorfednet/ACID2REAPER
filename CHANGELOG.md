# Changelog

All notable changes to **ACID2Reaper** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Release builds run `python scripts/verify_changelog.py` so every published version
must have a matching section below.

## [0.1.1] - 2026-03-22

Patch release: shared UTF-16LE string scanning (`string_scan`) used by `scan`, `acid_timeline`, and `acid_routing`; REAPER float formatting centralized in `rpp_format`; GUI uses grouped `LabelFrame` layout, clearer status wording, and theme foreground for status (no hard-coded hex colors). Tests added for string scan and float formatting.

## [0.1.0] - 2026-03-22

First public **Beta** release of **ACID2Reaper** (`acid2reaper` **0.1.0**): CLI and Tk desktop conversion from ACID (`.acd`, `.acd-bak`, `.acd-zip`) to Cockos REAPER (`.rpp`), heuristic and fingerprinted parsing, security limits on project and ZIP handling, PyInstaller bundles for macOS (`.app` / `.dmg`), Windows (folder + `ACID2Reaper-windows.zip`), and Linux (tarball), GitHub CI plus tag-based wheel/sdist and release automation, project documentation, and **CC BY 4.0** licensing.
