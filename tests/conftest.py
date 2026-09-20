"""Shared fixtures and opt-in markers for the ACID2Reaper test suite."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture(scope="session")
def drum_roll_path(fixtures_dir: Path) -> Path:
    return fixtures_dir / "DrumRollUpDemo.acd"


@pytest.fixture(scope="session")
def drum_roll_bytes(drum_roll_path: Path) -> bytes:
    return drum_roll_path.read_bytes()


@pytest.fixture
def isolated_acd_zip(tmp_path: Path, fixtures_dir: Path) -> Path:
    """
    An ACD-ZIP copied into ``tmp_path`` before use.

    ``containers.extract_acd_zip`` writes its ``*_acd_extracted/`` output next to
    the archive, so converting the committed copy pollutes ``tests/fixtures/``.
    A ``.gitignore`` rule hid that for a long time; ``_no_repo_writes`` below now
    fails the run instead.
    """
    dst = tmp_path / "DrumRollUpDemo.acd-zip"
    shutil.copy(fixtures_dir / "DrumRollUpDemo.acd-zip", dst)
    return dst


def _fixture_tree() -> list[str]:
    return sorted(str(p.relative_to(FIXTURES)) for p in FIXTURES.rglob("*"))


@pytest.fixture(scope="session", autouse=True)
def _no_repo_writes():
    """Fail the session if any test creates or removes a file under tests/fixtures/."""
    before = _fixture_tree()
    yield
    after = _fixture_tree()
    if after != before:
        added = sorted(set(after) - set(before))
        removed = sorted(set(before) - set(after))
        raise AssertionError(
            "tests mutated the repository fixture tree "
            f"(added={added}, removed={removed}); write to tmp_path instead"
        )


def pytest_collection_modifyitems(config, items):
    """Skip opt-in suites unless their environment switch is set."""
    corpus_dir = os.environ.get("ACID2REAPER_CORPUS_DIR")
    corpus_ok = bool(corpus_dir) and Path(corpus_dir).is_dir()
    net_ok = os.environ.get("ACID2REAPER_ALLOW_NETWORK") == "1"

    reaper_ok = False
    if os.environ.get("ACID2REAPER_REAPER_ORACLE") == "1":
        from fixturelib.reaper_oracle import reaper_binary

        reaper_ok = reaper_binary() is not None

    skips = {
        "corpus": pytest.mark.skip(reason="set ACID2REAPER_CORPUS_DIR to a directory of ACID projects"),
        "network": pytest.mark.skip(reason="set ACID2REAPER_ALLOW_NETWORK=1 to allow network access"),
        "reaper": pytest.mark.skip(reason="set ACID2REAPER_REAPER_ORACLE=1 with REAPER installed"),
    }
    ok = {"corpus": corpus_ok, "network": net_ok, "reaper": reaper_ok}
    for item in items:
        for marker, allowed in ok.items():
            if marker in item.keywords and not allowed:
                item.add_marker(skips[marker])
