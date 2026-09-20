"""
Convert a local folder of real ACID projects end to end.

Opt in with ``ACID2REAPER_CORPUS_DIR=/path/to/projects``. Skipped otherwise, and
always skipped in CI, because the projects it needs are private files that are
not in this repository. ``tests/test_corpus_manifest.py`` is the offline
counterpart that runs everywhere.

    ACID2REAPER_CORPUS_DIR=~/Music python -m pytest -m corpus -q
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

import pytest

from acid2reaper.binary.wave64 import extract_acid_wave64_timeline, parse_wave64_tree
from acid2reaper.cli import convert
from fixturelib.rpp_assert import assert_valid_rpp

pytestmark = pytest.mark.corpus

PROJECT_SUFFIXES = {".acd", ".acd-bak", ".acd-zip"}


def _corpus_projects() -> List[Path]:
    root = os.environ.get("ACID2REAPER_CORPUS_DIR")
    if not root:
        return []
    base = Path(root).expanduser()
    if not base.is_dir():
        return []
    return sorted(p for p in base.rglob("*") if p.is_file() and p.suffix.lower() in PROJECT_SUFFIXES)


CORPUS = _corpus_projects()


def _ids(path: Path) -> str:
    return path.name


@pytest.fixture(scope="session")
def corpus() -> List[Path]:
    if not CORPUS:
        pytest.skip("ACID2REAPER_CORPUS_DIR is empty or unset")
    return CORPUS


@pytest.mark.slow
@pytest.mark.parametrize("project", CORPUS, ids=_ids)
def test_project_converts_cleanly(project: Path, tmp_path: Path) -> None:
    """Every real project must convert, and produce a structurally valid file."""
    out = tmp_path / (project.stem + ".rpp")
    convert(project, out)
    text = out.read_text(encoding="utf-8")
    assert_valid_rpp(text)


@pytest.mark.slow
@pytest.mark.parametrize("project", CORPUS, ids=_ids)
def test_no_track_is_lost_or_starved(project: Path, tmp_path: Path) -> None:
    """
    Track count is preserved, and no project loses all of its media references.

    Both used to fail: event-less tracks were dropped, renumbering everything
    after them, and newer build layouts hid the media path so every track
    collapsed onto one fallback file.
    """
    raw = project.read_bytes()
    if not raw.startswith(b"riff") or parse_wave64_tree(raw) is None:
        pytest.skip("not a Wave64 ACID shell")
    timeline = extract_acid_wave64_timeline(raw)
    if timeline is None:
        pytest.skip("no decodable timeline")

    assert any(t.media_path for t in timeline.tracks), "every track lost its media reference"

    out = tmp_path / (project.stem + ".rpp")
    convert(project, out)
    text = out.read_text(encoding="utf-8")
    # One master track plus one per decoded track.
    assert text.count("<TRACK") == 1 + len(timeline.tracks)


def test_corpus_is_large_enough_to_be_worth_running(corpus: List[Path]) -> None:
    assert len(corpus) >= 10, "point ACID2REAPER_CORPUS_DIR at a real project folder"
