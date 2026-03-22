# Contributing to ACID2Reaper

Thank you for your interest in improving **ACID2Reaper** (currently the **first public beta**, 0.1.x).

## Ground rules

- Follow the [Code of Conduct](CODE_OF_CONDUCT.md).
- Prefer small, focused pull requests with a clear description of **what** and **why**.
- Run tests locally: `pytest` (with `pip install ".[dev]"`).

## Changelog (required for user-visible changes)

This project uses [Keep a Changelog](https://keepachangelog.com/) in [CHANGELOG.md](CHANGELOG.md).

- For any change that affects **users** (features, fixes, security, packaging), add a **`[Unreleased]`** note or a new `## [x.y.z]` section when preparing a release.
- Release builds run `python scripts/verify_changelog.py`; the current `pyproject.toml` **version** must have a matching `## [x.y.z]` heading in `CHANGELOG.md`.

## Releases (maintainers)

Git tags for GitHub should use a **`v` prefix** and semver; use **pre-release** tag names (e.g. `v0.2.0-beta.1`) when the build is not meant for production. See [RELEASING.md](RELEASING.md).

## Development setup

```bash
git clone https://github.com/gorfednet/ACID2Reaper.git
cd ACID2Reaper
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Pull requests

- Link related issues when applicable.
- Update **CHANGELOG.md** for user-facing changes (see above).
- Do not commit secrets, large binaries, or `dist/` / `build/` output.
