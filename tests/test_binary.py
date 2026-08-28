from __future__ import annotations

from pathlib import Path

from acid2reaper.binary.extract import extract_structured_fields
from acid2reaper.binary.fingerprint import detect_fingerprint
from acid2reaper.binary.riff import parse_riff_tree
from acid2reaper.binary.wave64 import (
    EVENT_LIST_FORM_GUID,
    extract_acid_wave64_timeline,
    iter_wave64_nodes,
    parse_wave64_tree,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


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


def test_wave64_rejects_chunk_past_container_end() -> None:
    raw = bytearray((FIXTURES / "DrumRollUpDemo.acd").read_bytes())
    raw[56:64] = (len(raw) + 1).to_bytes(8, "little")
    assert parse_wave64_tree(bytes(raw)) is None
