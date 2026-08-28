from __future__ import annotations

import struct
from pathlib import Path

import pytest

from acid2reaper.binary.extract import extract_structured_fields
from acid2reaper.binary.fingerprint import detect_fingerprint
from acid2reaper.binary.riff import parse_riff_tree
from acid2reaper.binary.wave64 import (
    EVENT_LIST_FORM_GUID,
    SOURCE_ACID_GUID,
    extract_acid_wave64_timeline,
    iter_wave64_nodes,
    parse_wave64_tree,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"

# Offset of the cached source "acid" chunk payload inside the ACID 3 fixture,
# derived from the parsed tree: the 5c538752 leaf at 2312 plus its 24-byte
# Wave64 header. See data/acd_signatures.json -> wave64_layout.
SOURCE_ACID_PAYLOAD_OFFSET = 2336
SOURCE_TEMPO_OFFSET = SOURCE_ACID_PAYLOAD_OFFSET + 28


def test_acid3_fingerprint_and_offsets() -> None:
    raw = (FIXTURES / "DrumRollUpDemo.acd").read_bytes()
    fp = detect_fingerprint(raw)
    assert fp.family_id == "riff_lower_guid_shell"
    assert fp.acid_pro_major_guess == 3
    assert fp.guid_at_24 == "ea1c076d-efa3-4c78-9057-7f79ee252aae"

    _fp2, structured = extract_structured_fields(raw)
    assert structured.signature_id == "sonic_foundry_acid3_drums_2001"
    assert structured.tempo_bpm == 120.0
    assert structured.sample_rate_hz == 44100


def test_acid3_not_standard_riff_container() -> None:
    """Sonic Foundry ACID3 demo uses a lowercase 'riff' shell with an invalid RIFF size field."""
    raw = (FIXTURES / "DrumRollUpDemo.acd").read_bytes()
    assert parse_riff_tree(raw, 0) is None


def test_acid3_wave64_event_tree_and_timing() -> None:
    raw = (FIXTURES / "DrumRollUpDemo.acd").read_bytes()
    tree = parse_wave64_tree(raw)
    assert tree is not None
    assert any(node.form_guid == EVENT_LIST_FORM_GUID for node in iter_wave64_nodes(tree))

    timeline = extract_acid_wave64_timeline(raw)
    assert timeline is not None
    assert timeline.ppq == 24576
    assert timeline.tempo_bpm == 120.0
    assert timeline.sample_rate_hz == 44100
    assert len(timeline.tracks) == 1
    assert timeline.tracks[0].media_path == "Break Pattern c.WAV"
    assert [(event.position_ticks, event.length_ticks) for event in timeline.tracks[0].events] == [
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


def test_source_acid_chunk_is_verbatim_copy_of_source_wav_acid_chunk() -> None:
    """
    The 5c538752 leaf caches the source file's own ACID 'acid' RIFF chunk.

    This is the evidence the cached-tempo offsets rest on: the 24 payload bytes
    after the leaf's 8-byte record header are byte-identical to the 'acid' chunk
    in the WAV the project references, so the standard chunk's field offsets
    apply directly.
    """
    raw = (FIXTURES / "DrumRollUpDemo.acd").read_bytes()
    wav = (FIXTURES / "samples" / "acid3_extracted" / "Break Pattern c.WAV").read_bytes()

    wav_acid = None
    offset = 12
    while offset + 8 <= len(wav):
        chunk_id = wav[offset : offset + 4]
        size = struct.unpack_from("<I", wav, offset + 4)[0]
        if chunk_id == b"acid":
            wav_acid = wav[offset + 8 : offset + 8 + size]
            break
        offset += 8 + size + (size & 1)

    assert wav_acid is not None, "source WAV must carry a standard 'acid' chunk"
    assert len(wav_acid) == 24
    cached = raw[SOURCE_ACID_PAYLOAD_OFFSET + 8 : SOURCE_ACID_PAYLOAD_OFFSET + 8 + 24]
    assert cached == wav_acid
    # Independent cross-check: 4 beats over the WAV's audio duration.
    assert struct.unpack_from("<f", cached, 20)[0] == pytest.approx(
        4 * 60.0 / (303360 / 4 / 44100.0), rel=1e-6
    )


def test_acid3_cached_source_loop_tempo() -> None:
    raw = (FIXTURES / "DrumRollUpDemo.acd").read_bytes()
    timeline = extract_acid_wave64_timeline(raw)
    assert timeline is not None

    tree = parse_wave64_tree(raw)
    assert tree is not None
    leaves = [
        node
        for node in iter_wave64_nodes(tree)
        if node.guid == SOURCE_ACID_GUID and node.form_guid is None
    ]
    assert len(leaves) == 1
    assert leaves[0].payload_offset == SOURCE_ACID_PAYLOAD_OFFSET

    source_loop = timeline.tracks[0].source_loop
    assert source_loop is not None
    assert source_loop.tempo_bpm == pytest.approx(139.5569610595703)
    assert source_loop.beats == 4
    # 4/4 in the only sample, so field order is untested by design.
    assert source_loop.time_sig_num == 4
    assert source_loop.time_sig_den == 4


def test_source_loop_absent_when_chunk_guid_missing() -> None:
    """With no 5c538752 leaf the timeline still parses and reports no source loop."""
    raw = bytearray((FIXTURES / "DrumRollUpDemo.acd").read_bytes())
    # Flip one byte of the leaf's GUID; the enclosing list form GUID is untouched
    # so chunk sizes and the rest of the tree stay valid.
    raw[2312] ^= 0xFF
    timeline = extract_acid_wave64_timeline(bytes(raw))
    assert timeline is not None
    assert timeline.tracks[0].source_loop is None
    assert len(timeline.tracks[0].events) == 15


def test_source_loop_rejects_implausible_cached_tempo() -> None:
    """An out-of-range cached tempo is discarded rather than trusted."""
    raw = bytearray((FIXTURES / "DrumRollUpDemo.acd").read_bytes())
    struct.pack_into("<f", raw, SOURCE_TEMPO_OFFSET, 0.0)
    assert extract_acid_wave64_timeline(bytes(raw)).tracks[0].source_loop is None

    struct.pack_into("<f", raw, SOURCE_TEMPO_OFFSET, float("nan"))
    assert extract_acid_wave64_timeline(bytes(raw)).tracks[0].source_loop is None

    struct.pack_into("<f", raw, SOURCE_TEMPO_OFFSET, 1.0e9)
    assert extract_acid_wave64_timeline(bytes(raw)).tracks[0].source_loop is None


def test_wave64_rejects_chunk_past_container_end() -> None:
    raw = bytearray((FIXTURES / "DrumRollUpDemo.acd").read_bytes())
    raw[56:64] = (len(raw) + 1).to_bytes(8, "little")
    assert parse_wave64_tree(bytes(raw)) is None
