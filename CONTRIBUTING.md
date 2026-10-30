# Contributing to ACID2Reaper

ACID2Reaper is in beta (0.2.x), and contributions are welcome.

## Ground rules

- Follow the [Code of Conduct](CODE_OF_CONDUCT.md).
- Keep pull requests small and focused, and describe **what** changed and **why**.
- Run the tests locally with `pytest` (after `pip install ".[dev]"`).
- Run the linter with `ruff check src tests scripts`.

## Tests

The default suite is fast and needs nothing but the repository:

```bash
pytest
ruff check src tests scripts
```

Three suites are opt-in. Each needs something this repository doesn't
ship, and each is skipped without it:

| Suite | Enable with | Needs |
| --- | --- | --- |
| Real-project corpus | `ACID2REAPER_CORPUS_DIR=/path/to/projects` | A folder of real `.acd` files |
| REAPER oracle | `ACID2REAPER_REAPER_ORACLE=1` | A local REAPER install; attended, as an unlicensed REAPER shows a nag dialog |
| Network harvesting | `ACID2REAPER_ALLOW_NETWORK=1` | Internet access |

If a change alters converter output on purpose, read the diff and regenerate
the golden projects:

```bash
python scripts/update_goldens.py
```

CI runs `python scripts/update_goldens.py --check`, so a golden project can't change without a reviewed diff.

### Contributing format knowledge

The most useful contribution is a real `.acd` file that covers something the
current corpus doesn't. A genuine x/8 project is the first need, because the
quarter-note tempo assumption in `acid_timing.seconds_per_tick` can't be
settled without one. Please attach it to an issue.

If you can't share the file itself, `scripts/build_corpus_manifest.py` reduces
a folder of projects to structural fingerprints (no audio, no file names, no
project bytes), which is enough to extend coverage.

## Changelog (required for user-visible changes)

This project uses [Keep a Changelog](https://keepachangelog.com/) in [CHANGELOG.md](CHANGELOG.md).

- Any change that affects **users** (features, fixes, security, packaging) needs an **`[Unreleased]`** note, or a new `## [x.y.z]` section when you prepare a release.
- Release builds run `python scripts/verify_changelog.py`. The `pyproject.toml` **version** must have a matching `## [x.y.z]` heading in `CHANGELOG.md`.

## Releases (maintainers)

Git tags for GitHub use a **`v` prefix** and semver. Use a **pre-release** tag name (for example `v0.2.0-beta.1`) when the build isn't meant for production. See [RELEASING.md](RELEASING.md).

## Development setup

```bash
git clone https://github.com/gorfednet/ACID2REAPER.git
cd ACID2Reaper
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Pull requests

- Link related issues.
- Update **CHANGELOG.md** for user-facing changes (see above).
- Don't commit secrets, large binaries, or `dist/` or `build/` output.
