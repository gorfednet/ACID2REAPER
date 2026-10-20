# Pull request review (ACID2REAPER)

Read by the Claude reviewer (`.github/workflows/claude-review.yml`, which calls gorfednet/.github's shared workflow) on every non-draft pull request and on a `claude review` comment. The shared workflow says what to report in general; this file holds what is particular to this repository.

## What this repository is

A Python tool (CLI and Tkinter GUI) that converts Sonic Foundry, Sony and MAGIX ACID projects (`.acd`, `.acd-bak`, `.acd-zip`) to Cockos REAPER `.rpp` projects. It is in beta (0.2.x). Releases are built by pushing a `v*.*.*` tag, which runs `release.yml` and attaches an sdist and wheel to a GitHub Release; PyInstaller recipes in `packaging/` build the desktop apps.

## House rules to hold the change to

- A change that alters converter output on purpose regenerates the golden projects with `python scripts/update_goldens.py`, and the diff is read. CI runs `update_goldens.py --check`, so an unreviewed golden is a finding.
- A user-visible change adds a `[Unreleased]` note or a `## [x.y.z]` section to `CHANGELOG.md`. The `pyproject.toml` version, `src/acid2reaper/_version.py` and the changelog heading must agree (`scripts/verify_changelog.py`).
- Tags use a `v` prefix and semver, with a pre-release label such as `-beta.1` when not for production (`RELEASING.md`).
- Chunk roles and offsets are catalogued in `src/acid2reaper/data/acd_signatures.json`. A decoded field changes that catalogue, a fixture and a test together. Undecoded chunks are not invented into output.
- Input safety limits stay: file and ZIP size caps, path validation, and sanitized paths in exported RPP (`tests/test_security.py`). A change must not loosen them.
- The default test suite needs only the repository. The corpus, REAPER oracle and network suites stay opt-in (`ACID2REAPER_CORPUS_DIR`, `ACID2REAPER_REAPER_ORACLE`, `ACID2REAPER_ALLOW_NETWORK`). The corpus manifest holds structural fingerprints only: no audio, file names or project bytes.
- Coverage stays at or above the `--cov-fail-under=75` in `ci.yml`; `ruff check src tests scripts` passes. Python 3.9 stays supported.
- No secrets, SSH keys, large binaries, or `dist/` and `build/` output in the repository.
- Pull requests are small and focused, with a clear what and why.

## Where the rules live

- `README.md`, `CONTRIBUTING.md`, `RELEASING.md`, `SECURITY.md`, `CHANGELOG.md`, `packaging/BUILD.md`
- `pyproject.toml` (ruff, pytest, coverage settings)
- `.github/workflows/ci.yml`, `.github/workflows/release.yml`
- `scripts/verify_changelog.py`, `scripts/update_goldens.py`
