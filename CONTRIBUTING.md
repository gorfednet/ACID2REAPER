# Contributing to ACID2Reaper

Thank you for your interest in improving **ACID2Reaper** (currently in beta, 0.2.x).

## Ground rules

- Follow the [Code of Conduct](CODE_OF_CONDUCT.md).
- Prefer small, focused pull requests with a clear description of **what** and **why**.
- Run tests locally: `pytest` (with `pip install ".[dev]"`).
- Run the linter: `ruff check src tests scripts`.

## Tests

The default suite is fast and needs nothing but the repository:

```bash
pytest
ruff check src tests scripts
```

Three suites are opt-in, because they need something this repository does not
ship, and are skipped without it:

| Suite | Enable with | Needs |
| --- | --- | --- |
| Real-project corpus | `ACID2REAPER_CORPUS_DIR=/path/to/projects` | A folder of real `.acd` files |
| REAPER oracle | `ACID2REAPER_REAPER_ORACLE=1` | A local REAPER install; attended, as an unlicensed REAPER shows a nag dialog |
| Network harvesting | `ACID2REAPER_ALLOW_NETWORK=1` | Internet access |

If a change alters converter output on purpose, review the diff and regenerate
the golden projects:

```bash
python scripts/update_goldens.py
```

CI runs `python scripts/update_goldens.py --check`, so an unreviewed golden
cannot drift in.

### Contributing format knowledge

The most valuable contribution is a real `.acd` file that exercises something
the current corpus does not — a genuine x/8 project above all, since the
quarter-note tempo assumption in `acid_timing.seconds_per_tick` cannot be
settled without one. Please attach it to an issue.

If you cannot share the file itself, `scripts/build_corpus_manifest.py` reduces
a folder of projects to structural fingerprints — no audio, no file names, no
project bytes — which is enough to extend coverage.

## Changelog (required for user-visible changes)

This project uses [Keep a Changelog](https://keepachangelog.com/) in [CHANGELOG.md](CHANGELOG.md).

- For any change that affects **users** (features, fixes, security, packaging), add a **`[Unreleased]`** note or a new `## [x.y.z]` section when preparing a release.
- Release builds run `python scripts/verify_changelog.py`; the current `pyproject.toml` **version** must have a matching `## [x.y.z]` heading in `CHANGELOG.md`.

## Releases (maintainers)

Git tags for GitHub should use a **`v` prefix** and semver; use **pre-release** tag names (e.g. `v0.2.0-beta.1`) when the build is not meant for production. See [RELEASING.md](RELEASING.md).

## Development setup

```bash
git clone https://github.com/gorfednet/ACID2REAPER.git
cd ACID2Reaper
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Pull requests

- Link related issues when applicable.
- Update **CHANGELOG.md** for user-facing changes (see above).
- Do not commit secrets, large binaries, or `dist/` / `build/` output.
