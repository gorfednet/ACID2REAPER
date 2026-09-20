"""
Check generated projects against a real REAPER install.

Round-tripping through the ``rpp`` library only proves our writer and our reader
agree with each other. This asks REAPER: load what we wrote, save it back, and
compare what it understood.

Opt in with ``ACID2REAPER_REAPER_ORACLE=1``; skipped by default and in CI. Runs
are attended, because an unlicensed REAPER shows an evaluation nag that does not
dismiss itself.

    ACID2REAPER_REAPER_ORACLE=1 python -m pytest -m reaper -q
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fixturelib.matrix import CASES
from fixturelib.reaper_oracle import compare_with_reaper, project_rpp, reaper_binary

pytestmark = [pytest.mark.reaper, pytest.mark.slow]

# The meters are where REAPER's own opinion matters most, so lead with those.
ORACLE_CASES = [c for c in CASES if c.id.startswith("m") or c.id in {"one_shot", "stretched_loop"}]


def test_reaper_is_present() -> None:
    assert reaper_binary() is not None


@pytest.mark.parametrize("case", ORACLE_CASES, ids=lambda c: c.id)
def test_reaper_agrees_with_our_project(case, tmp_path: Path) -> None:
    from test_golden_rpp import render_case as render

    text = render(case, tmp_path)
    ours = tmp_path / f"{case.id}.oracle.rpp"
    ours.write_text(text.replace("<TMP>", str(tmp_path)), encoding="utf-8")

    differences = compare_with_reaper(ours)
    assert differences == {}, f"{case.id}: REAPER read this differently: {differences}"


def test_projection_ignores_formatting_only_changes() -> None:
    """
    REAPER rewrites the whole document with its own defaults.

    The comparison is deliberately a projection: asserting on raw text would
    fail on whitespace and default lines that carry no musical meaning.
    """
    base = (Path(__file__).resolve().parent / "fixtures" / "golden" / "m7_8.rpp").read_text()
    reordered = base.replace("  RIPPLE 0\n", "  RIPPLE 0\n  AUTOXFADE 0\n", 1)
    assert project_rpp(base) == project_rpp(reordered)
