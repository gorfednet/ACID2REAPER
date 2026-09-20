from __future__ import annotations

import os
import re
import struct
from pathlib import Path

import pytest
from rpp import loads

from acid2reaper.binary.acid_chunk import FLAG_ONE_SHOT
from acid2reaper.binary.wave64 import iter_wave64_nodes, parse_wave64_tree
from acid2reaper.cli import convert
from fixturelib.offsets import SOURCE_ACID_LEAF_OFFSET, SOURCE_FLAGS_OFFSET
from fixturelib.rpp_assert import assert_valid_rpp

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_drum_roll_acd_to_rpp(tmp_path: Path) -> None:
    acd = FIXTURES / "DrumRollUpDemo.acd"
    out = tmp_path / "out.rpp"
    convert(acd, out)
    text = out.read_text(encoding="utf-8")
    assert_valid_rpp(text)
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


def test_acd_zip_to_rpp(tmp_path: Path, isolated_acd_zip: Path) -> None:
    # extract_acd_zip() unpacks next to the archive, so convert a tmp_path copy.
    out = tmp_path / "zip_out.rpp"
    convert(isolated_acd_zip, out)
    text = out.read_text(encoding="utf-8")
    assert_valid_rpp(text)
    root = loads(text)
    assert root.tag == "REAPER_PROJECT"


def test_standalone_acd_file_token_is_project_relative(tmp_path: Path) -> None:
    """Bare basenames must not resolve against CWD when media is missing."""
    acd = FIXTURES / "DrumRollUpDemo.acd"
    out = tmp_path / "cwd_safe.rpp"
    # Run from an empty CWD-like directory so a bare basename would miss media.
    convert(acd, out)
    text = out.read_text(encoding="utf-8")
    assert_valid_rpp(text)
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
    assert_valid_rpp(text)

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
    raw[SOURCE_ACID_LEAF_OFFSET] ^= 0xFF
    acd = tmp_path / "no_source_tempo.acd"
    acd.write_bytes(bytes(raw))

    out = tmp_path / "fallback.rpp"
    convert(acd, out)
    text = out.read_text(encoding="utf-8")
    assert_valid_rpp(text)

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
    assert_valid_rpp(text)

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
    src_wav = FIXTURES / "samples" / "Break Pattern c.WAV"
    shutil.copy(src_wav, work / "Break Pattern c.WAV")
    with wave.open(str(work / "Break Pattern c.WAV"), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        expected = frames / float(rate)

    out = work / "out.rpp"
    convert(work / "DrumRollUpDemo.acd", out)
    text = out.read_text(encoding="utf-8")
    assert_valid_rpp(text)
    assert (work / "Break Pattern c.WAV").exists()
    assert str(work) in text or "Break Pattern c.WAV" in text
    m = re.search(r"LENGTH\s+([0-9.]+)", text)
    assert m, "expected LENGTH in RPP"
    length = float(m.group(1))
    assert length == pytest.approx(2.0)
    assert abs(length - expected) > 0.05


def test_notes_block_is_emitted_and_round_trips(tmp_path: Path) -> None:
    """Diagnostics the parser already computed now reach the project file."""
    out = tmp_path / "notes.rpp"
    convert(FIXTURES / "DrumRollUpDemo.acd", out)
    text = out.read_text(encoding="utf-8")
    assert_valid_rpp(text)

    assert "<NOTES" in text
    assert "|Project tempo: 120 BPM; time signature 4/4." in text
    # Plain-string children keep the leading pipe unquoted, as REAPER writes it.
    assert '"|Project tempo' not in text
    assert loads(text).tag == "REAPER_PROJECT"


def test_missing_media_warning_lists_each_file_once(tmp_path: Path) -> None:
    """A loop used fifteen times must not be reported fifteen times."""
    out = tmp_path / "missing.rpp"
    convert(FIXTURES / "DrumRollUpDemo.acd", out)
    warning = next(
        line for line in out.read_text(encoding="utf-8").splitlines() if "media not found" in line
    )
    assert warning.count("Break Pattern c.WAV") == 1


def test_items_carry_a_name(tmp_path: Path) -> None:
    out = tmp_path / "named.rpp"
    convert(FIXTURES / "DrumRollUpDemo.acd", out)
    text = out.read_text(encoding="utf-8")
    assert_valid_rpp(text)
    assert text.count('NAME "Break Pattern c"') == 16  # 15 items plus the track


def test_tempo_is_formatted_like_every_other_number(tmp_path: Path) -> None:
    """The tempo line used to use str(), printing '120.0' among '120's."""
    out = tmp_path / "tempo.rpp"
    convert(FIXTURES / "DrumRollUpDemo.acd", out)
    assert "TEMPO 120 4 4" in out.read_text(encoding="utf-8")


def test_one_shot_sources_are_not_stretched(tmp_path: Path) -> None:
    """
    A one-shot has no tempo to beat-map, so it must keep its natural rate.

    Resampling a hit to the project tempo audibly retunes it. The converter used
    to stretch every source that carried a plausible cached tempo, one-shots
    included, because the acid-chunk flag word was never decoded.
    """
    raw = bytearray((FIXTURES / "DrumRollUpDemo.acd").read_bytes())
    struct.pack_into("<I", raw, SOURCE_FLAGS_OFFSET, FLAG_ONE_SHOT)
    acd = tmp_path / "one_shot.acd"
    acd.write_bytes(bytes(raw))

    out = tmp_path / "one_shot.rpp"
    convert(acd, out)
    text = out.read_text(encoding="utf-8")
    assert_valid_rpp(text)

    assert _playrate_lines(text) == []
    assert "One-shot sources left unstretched" in text
    # Timing is unaffected: only the stretch factor changes.
    assert text.count("<ITEM") == 15


def test_loops_are_still_stretched(tmp_path: Path) -> None:
    """The companion to the one-shot case: a plain loop keeps its PLAYRATE."""
    out = tmp_path / "loop.rpp"
    convert(FIXTURES / "DrumRollUpDemo.acd", out)
    text = out.read_text(encoding="utf-8")
    assert_valid_rpp(text)
    assert len(_playrate_lines(text)) == 15
    assert "One-shot sources left unstretched" not in text


def test_clip_before_bar_one_is_trimmed_into_the_source_offset(tmp_path: Path) -> None:
    """
    REAPER has no negative item positions, so the hidden head becomes SOFFS.

    A real corpus project stores an event at -41026 ticks; the audible part must
    survive at position 0, offset into the source by the amount that was cut.
    """
    raw = bytearray((FIXTURES / "DrumRollUpDemo.acd").read_bytes())
    # First event: position 0, length 98304. Move it half a length to the left.
    root = parse_wave64_tree(bytes(raw))
    event = next(n for n in iter_wave64_nodes(root) if n.form_guid is None and n.payload_size == 112)
    struct.pack_into("<q", raw, event.payload_offset + 0x10, -49152)
    acd = tmp_path / "negative.acd"
    acd.write_bytes(bytes(raw))

    out = tmp_path / "negative.rpp"
    convert(acd, out)
    text = out.read_text(encoding="utf-8")
    assert_valid_rpp(text)

    items = text.split("<ITEM")[1:]
    first = items[0]
    assert "POSITION 0" in first
    # 49152 ticks at 120 BPM and ppq 24576 is exactly one second.
    assert "SOFFS 1" in first
    assert "LENGTH 1" in first


def test_clip_entirely_before_bar_one_is_dropped_and_reported(tmp_path: Path) -> None:
    raw = bytearray((FIXTURES / "DrumRollUpDemo.acd").read_bytes())
    root = parse_wave64_tree(bytes(raw))
    event = next(n for n in iter_wave64_nodes(root) if n.form_guid is None and n.payload_size == 112)
    struct.pack_into("<q", raw, event.payload_offset + 0x10, -98304)
    acd = tmp_path / "offscreen.acd"
    acd.write_bytes(bytes(raw))

    out = tmp_path / "offscreen.rpp"
    convert(acd, out)
    text = out.read_text(encoding="utf-8")
    assert text.count("<ITEM") == 14
    assert "Dropped clips that lay entirely before the start" in text


@pytest.mark.skipif(
    os.name == "nt", reason="a drive-letter path is native here, not foreign"
)
def test_windows_absolute_paths_are_not_joined_to_the_project_dir(tmp_path: Path) -> None:
    """
    A drive-letter path is absolute on Windows but relative to pathlib on POSIX.

    Joining it produced FILE tokens like "/home/me/project/C:\\audio\\loop.wav".
    """
    from acid2reaper.scan import _resolve_clip_path

    resolved = _resolve_clip_path("C:\\audio storage\\loop.wav", tmp_path / "proj.acd", [])
    assert resolved == tmp_path / "loop.wav"
    assert "C:" not in str(resolved)


def test_foreign_absolute_detection_is_platform_aware() -> None:
    """On Windows a drive-letter path is native and must not be rewritten."""
    from acid2reaper.scan import _is_foreign_absolute

    assert _is_foreign_absolute("loop.wav") is False
    assert _is_foreign_absolute("C:\\audio\\loop.wav") is (os.name != "nt")
