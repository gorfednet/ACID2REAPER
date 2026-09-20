"""Unit tests for the shared ``acid`` RIFF chunk decoder."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from acid2reaper.binary.acid_chunk import (
    ACID_CHUNK_BYTES,
    FLAG_ACIDIZER,
    FLAG_ONE_SHOT,
    FLAG_ROOT_NOTE_SET,
    AcidChunk,
    find_acid_chunk_in_riff,
    pack_acid_chunk,
    parse_acid_chunk,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_decodes_the_real_source_wav() -> None:
    wav = (FIXTURES / "samples" / "Break Pattern c.WAV").read_bytes()
    chunk = find_acid_chunk_in_riff(wav)
    assert chunk == AcidChunk(
        flags=0,
        root_note=0x3C,
        reserved_u16=0x8000,
        reserved_f32=0.0,
        beats=4,
        meter_den=4,
        meter_num=4,
        tempo_bpm=pytest.approx(139.5569610595703),
    )


def test_packs_back_to_the_real_bytes() -> None:
    """The packer must reproduce the chunk that is actually in the file."""
    wav = (FIXTURES / "samples" / "Break Pattern c.WAV").read_bytes()
    offset = wav.find(b"acid")
    raw = wav[offset + 8 : offset + 8 + ACID_CHUNK_BYTES]
    assert pack_acid_chunk(find_acid_chunk_in_riff(wav)) == raw


@pytest.mark.parametrize(
    "flags, one_shot, root_set, acidizer",
    [
        (0x00, False, False, False),
        (FLAG_ONE_SHOT, True, False, False),
        (FLAG_ROOT_NOTE_SET, False, True, False),
        (FLAG_ONE_SHOT | FLAG_ROOT_NOTE_SET | FLAG_ACIDIZER, True, True, True),
    ],
)
def test_flag_bits(flags: int, one_shot: bool, root_set: bool, acidizer: bool) -> None:
    chunk = AcidChunk(flags=flags)
    assert chunk.one_shot is one_shot
    assert chunk.root_note_set is root_set
    assert chunk.set_by_acidizer is acidizer


def test_root_note_is_gated_on_its_flag() -> None:
    assert AcidChunk(flags=0, root_note=60).effective_root_note is None
    assert AcidChunk(flags=FLAG_ROOT_NOTE_SET, root_note=60).effective_root_note == 60


@pytest.mark.parametrize("tempo", [0.0, -120.0, 19.9, 400.1, float("nan"), float("inf"), 1.0e9])
def test_implausible_tempo_is_rejected(tempo: float) -> None:
    blob = bytearray(pack_acid_chunk(AcidChunk()))
    struct.pack_into("<f", blob, 20, tempo)
    assert parse_acid_chunk(bytes(blob)) is None


@pytest.mark.parametrize("tempo", [20.0, 400.0, 139.5569610595703])
def test_boundary_tempos_are_accepted(tempo: float) -> None:
    chunk = parse_acid_chunk(pack_acid_chunk(AcidChunk(tempo_bpm=tempo)))
    assert chunk is not None
    assert chunk.tempo_bpm == pytest.approx(tempo)


def test_short_buffer_is_rejected() -> None:
    assert parse_acid_chunk(b"\x00" * (ACID_CHUNK_BYTES - 1)) is None
    assert parse_acid_chunk(pack_acid_chunk(AcidChunk()), offset=-1) is None


def test_non_riff_input_yields_no_chunk() -> None:
    assert find_acid_chunk_in_riff(b"") is None
    assert find_acid_chunk_in_riff(b"RIFF" + b"\x00" * 8) is None
