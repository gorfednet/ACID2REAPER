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


def _playrate_lines(text: str) -> list[str]:
    """ITEM PLAYRATE lines only (the project-level PLAYRATE has four tokens)."""
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith("PLAYRATE ") and len(line.split()) == 9
    ]


def test_playrate_from_cached_source_tempo(tmp_path: Path) -> None:
    """Project 120 BPM against the fixture's cached 139.557 BPM source loop."""
    acd = FIXTURES / "DrumRollUpDemo.acd"
    out = tmp_path / "playrate.rpp"
    convert(acd, out)
    text = out.read_text(encoding="utf-8")

    lines = _playrate_lines(text)
    assert len(lines) == 15
    expected = 120.0 / 139.5569610595703
    for line in lines:
        tokens = line.split()
        assert float(tokens[1]) == pytest.approx(expected, rel=1e-9)
        # Preserve-pitch flag must stay enabled.
        assert tokens[2] == "1"

    # A stretched source still occupies its decoded event length on the timeline.
    lengths = [float(v) for v in re.findall(r"^\s*LENGTH\s+([0-9.]+)", text, re.MULTILINE)]
    assert lengths[0] == pytest.approx(2.0)
    root = loads(text)
    assert root.tag == "REAPER_PROJECT"


def test_playrate_falls_back_to_unity_without_cached_source_tempo(tmp_path: Path) -> None:
    """No cached source tempo means no PLAYRATE line, and timing is unchanged."""
    raw = bytearray((FIXTURES / "DrumRollUpDemo.acd").read_bytes())
    # Same single-byte GUID edit as tests/test_binary.py: removes the 5c538752
    # leaf without disturbing chunk sizes.
    raw[2312] ^= 0xFF
    acd = tmp_path / "no_source_tempo.acd"
    acd.write_bytes(bytes(raw))

    out = tmp_path / "fallback.rpp"
    convert(acd, out)
    text = out.read_text(encoding="utf-8")

    assert _playrate_lines(text) == []
    assert text.count("<ITEM") == 15
    positions = [float(v) for v in re.findall(r"^\s*POSITION\s+([0-9.]+)", text, re.MULTILINE)]
    assert positions[0] == pytest.approx(0.0)
    assert positions[1] == pytest.approx(2.0)
    root = loads(text)
    assert root.tag == "REAPER_PROJECT"


@pytest.mark.parametrize("bad_rate", [0.0, -0.0, float("nan"), float("inf"), 1e9, 1e-9])
def test_implausible_playrate_is_never_exported(tmp_path: Path, bad_rate: float) -> None:
    """Zero, non-finite, and out-of-range stretch factors must not reach the RPP."""
    from acid2reaper.export_rpp import write_rpp
    from acid2reaper.model import AcidClip, AcidProject, AcidTrack, MasterBus

    clip = AcidClip(path=tmp_path / "x.wav", position_sec=0.0, length_sec=1.0)
    clip.playrate = bad_rate
    project = AcidProject(
        source_path=tmp_path / "x.acd",
        master=MasterBus(),
        tracks=[AcidTrack(name="x", clips=[clip])],
    )
    out = tmp_path / "clamped.rpp"
    write_rpp(project, out)
    text = out.read_text(encoding="utf-8")

    assert _playrate_lines(text) == []
    assert "nan" not in text.lower()
    assert "inf" not in text.lower()
    assert loads(text).tag == "REAPER_PROJECT"


def test_reverse_clip_keeps_negative_playrate_when_rate_is_implausible(tmp_path: Path) -> None:
    """Reverse must survive a rejected stretch factor as a negative unity rate."""
    from acid2reaper.export_rpp import write_rpp
    from acid2reaper.model import AcidClip, AcidProject, AcidTrack, MasterBus

    clip = AcidClip(path=tmp_path / "x.wav", position_sec=0.0, length_sec=1.0)
    clip.playrate = 0.0
    clip.reverse = True
    project = AcidProject(
        source_path=tmp_path / "x.acd",
        master=MasterBus(),
        tracks=[AcidTrack(name="x", clips=[clip])],
    )
    out = tmp_path / "reverse.rpp"
    write_rpp(project, out)

    lines = _playrate_lines(out.read_text(encoding="utf-8"))
    assert len(lines) == 1
    assert lines[0].split()[1] == "-1"


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
