from __future__ import annotations

from pathlib import Path

from acid2reaper.binary.extract import extract_structured_fields
from acid2reaper.binary.fingerprint import detect_fingerprint
from acid2reaper.binary.riff import parse_riff_tree

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
