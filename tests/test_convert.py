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
    root = loads(text)
    assert root.tag == "REAPER_PROJECT"


def test_acd_zip_to_rpp(tmp_path: Path) -> None:
    z = FIXTURES / "DrumRollUpDemo.acd-zip"
    out = tmp_path / "zip_out.rpp"
    convert(z, out)
    text = out.read_text(encoding="utf-8")
    root = loads(text)
    assert root.tag == "REAPER_PROJECT"
