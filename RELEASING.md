# Releasing ACID2Reaper

The current public line is the **first beta** (**0.1.2**). Future releases will follow the same process below.

## Version numbers (Python package)

The installable **package version** is plain [semantic versioning](https://semver.org/) in metadata (no `v` prefix), e.g. `0.1.2` in `pyproject.toml` and `src/acid2reaper/_version.py`.

1. Bump `src/acid2reaper/_version.py` (`__version__` and optional `__version_label__`).
2. Match `version = "..."` in `pyproject.toml`.
3. Add or update the `## [x.y.z] - YYYY-MM-DD` section in `CHANGELOG.md` (and clear **`[Unreleased]`** when you use it).
4. Run:

   ```bash
   python scripts/verify_changelog.py
   pytest
   ```

## Git tags (GitHub)

[GitHub recommends](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases) naming **git tags** with a leading **`v`**, then the version:

- **Stable / production:** `v1.0.0`, `v2.3.4`
- **Pre-release / not for production:** add a label after the version, e.g. `v0.2.0-alpha`, `v0.2.0-beta.3`, `v1.0.0-rc.1`

When you publish a [GitHub Release](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository), create or choose a tag that follows the above. Pre-releases can be marked as such in the GitHub UI as well.

Example annotated tag and push:

```bash
git tag -a v0.1.2 -m "ACID2Reaper 0.1.2 Beta"
git push origin v0.1.2
```

The tag’s numeric part should match the package version in `pyproject.toml` (e.g. package `0.1.2` → tag `v0.1.2` or a pre-release variant like `v0.1.2-beta.1`).

`.github/workflows/release.yml` runs on tags matching `v*.*.*`, which includes common pre-release tag names such as `v1.0.0-beta.1`.

## Binaries

See [packaging/BUILD.md](packaging/BUILD.md). Each platform script runs `verify_changelog.py` first.

## Automated build and deploy (GitHub Actions)

Pushing a matching **tag** triggers the workflow in [`.github/workflows/release.yml`](.github/workflows/release.yml):

1. **Tests** and **changelog** (`verify_changelog.py`) must pass.
2. **Artifacts:** `python -m build` produces the **sdist** and **wheel**.
3. **GitHub Release:** those files are attached and release notes are generated.

Install from the release (macOS / Linux often need `python3 -m pip`):

```bash
python3 -m pip install \
  https://github.com/gorfednet/ACID2REAPER/releases/download/v0.1.2/acid2reaper-0.1.2-py3-none-any.whl
```

Or from the tag without a wheel URL:

```bash
python3 -m pip install "acid2reaper @ git+https://github.com/gorfednet/ACID2REAPER.git@v0.1.2"
```

### PyPI (optional, deferred)

PyPI trusted publishing is **not** required for a release. When a PyPI login is available again, add a pending publisher for `gorfednet/ACID2REAPER` / `release.yml` and restore a `pypa/gh-action-pypi-publish` step (with `permissions: id-token: write`) after the build.

### Optional: TestPyPI

To exercise uploads without affecting the real index, add a separate job or workflow using `pypa/gh-action-pypi-publish` with `repository-url: https://test.pypi.org/legacy/` and configure a TestPyPI trusted publisher.

## Publish source to GitHub (push commits)

```bash
cd /path/to/ACID2Reaper
git add -A
git commit -m "Describe your change"
git push origin main
```

If the remote is missing:

```bash
git remote add origin https://github.com/gorfednet/ACID2REAPER.git
git push -u origin main
```
