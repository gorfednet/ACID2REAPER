from __future__ import annotations

from pathlib import Path

import pytest

from acid2reaper.cli import convert
from rpp import loads


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_drum_roll_acd_to_rpp(tmp_path: Path) -> None:
    acd = FIXTURES / "DrumRollUpDemo.acd"
    out = tmp_path / "out.rpp"
    convert(acd, out)
    text = out.read_text(encoding="utf-8")
    assert "REAPER_PROJECT" in text
    assert "Break Pattern" in text or "break pattern" in text.lower()
    # Known demo layout: half volume, -1 semitone pitch (see acid_timeline offsets).
    assert "VOLPAN 0.5 0 1 -1" in text
    assert "PITCHSHIFT -1 0 0 0 0 0" in text
    # Master bus + at least one audio track, each with FXCHAIN and routing lines.
    assert text.count("<FXCHAIN") >= 2
    assert "TRACKGROUP 0" in text
    assert "CHANMODE 0" in text
    root = loads(text)
    assert root.tag == "REAPER_PROJECT"


def test_acd_zip_to_rpp(tmp_path: Path) -> None:
    z = FIXTURES / "DrumRollUpDemo.acd-zip"
    out = tmp_path / "zip_out.rpp"
    convert(z, out)
    text = out.read_text(encoding="utf-8")
    root = loads(text)
    assert root.tag == "REAPER_PROJECT"
