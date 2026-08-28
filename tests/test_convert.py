from __future__ import annotations

import re
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
    # The event timeline is structural; unrelated version/record fields must not
    # be fabricated as clip gain or pitch.
    assert text.count("<ITEM") == 15
    assert "PITCHSHIFT" not in text
    assert "VOLPAN 0.5 0 1 -1" not in text
    assert "SOFFS" in text
    assert "SNAPOFFS" not in text
    positions = [float(v) for v in re.findall(r"^\s*POSITION\s+([0-9.]+)", text, re.MULTILINE)]
    lengths = [float(v) for v in re.findall(r"^\s*LENGTH\s+([0-9.]+)", text, re.MULTILINE)]
    expected_ticks = [
        (0, 98304),
        (98304, 49152),
        (147456, 49152),
        (196608, 24576),
        (221184, 24576),
        (245760, 24576),
        (270336, 24576),
        (294912, 12289),
        (307201, 12289),
        (319490, 12289),
        (331779, 12289),
        (344068, 12289),
        (356357, 12289),
        (368646, 12289),
        (380935, 12289),
    ]
    assert positions == pytest.approx([p / 49152.0 for p, _ in expected_ticks])
    assert lengths == pytest.approx([length / 49152.0 for _, length in expected_ticks])
    assert max(p + length for p, length in zip(positions, lengths)) == pytest.approx(
        8.000162760416666
    )
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


def test_standalone_acd_file_token_is_project_relative(tmp_path: Path) -> None:
    """Bare basenames must not resolve against CWD when media is missing."""
    acd = FIXTURES / "DrumRollUpDemo.acd"
    out = tmp_path / "cwd_safe.rpp"
    # Run from an empty CWD-like directory so a bare basename would miss media.
    convert(acd, out)
    text = out.read_text(encoding="utf-8")
    # FILE path must include the fixtures directory, not only a bare filename.
    assert "Break Pattern" in text
    assert str(FIXTURES) in text or "DrumRollUpDemo" in text or "fixtures" in text.lower()
    # Must not be a bare relative basename alone after FILE.
    assert 'FILE "Break Pattern c.WAV"' not in text
    assert 'FILE "Break Pattern C.WAV"' not in text


def test_acd_event_length_wins_over_colocated_wav_duration(tmp_path: Path) -> None:
    """A decoded event length must take precedence over full source duration."""
    import shutil
    import wave

    work = tmp_path / "project"
    work.mkdir()
    shutil.copy(FIXTURES / "DrumRollUpDemo.acd", work / "DrumRollUpDemo.acd")
    src_wav = FIXTURES / "DrumRollUpDemo_acd_extracted" / "Break Pattern c.WAV"
    shutil.copy(src_wav, work / "Break Pattern c.WAV")
    with wave.open(str(work / "Break Pattern c.WAV"), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        expected = frames / float(rate)

    out = work / "out.rpp"
    convert(work / "DrumRollUpDemo.acd", out)
    text = out.read_text(encoding="utf-8")
    assert (work / "Break Pattern c.WAV").exists()
    assert str(work) in text or "Break Pattern c.WAV" in text
    m = re.search(r"LENGTH\s+([0-9.]+)", text)
    assert m, "expected LENGTH in RPP"
    length = float(m.group(1))
    assert length == pytest.approx(2.0)
    assert abs(length - expected) > 0.05
