"""
Check our ``acid`` chunk encoding against chunks nobody here wrote.

The committed fixture shows we can read one chunk. These records come from a
Sonic Foundry loop disc, harvested by ``scripts/harvest_acid_chunks.py``. The
manifest holds decoded fields and a SHA-256 of each 24-byte chunk -- no audio,
no file names, no chunk bytes.

The digest is what makes this worth having. Re-packing a record with the shipped
encoder has to reproduce the hash of the bytes that were on the disc, so the
offsets are checked against real files rather than against our own assumptions.
"""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

import pytest

from acid2reaper.binary.acid_chunk import (
    ACID_CHUNK_BYTES,
    KNOWN_FLAGS,
    AcidChunk,
    pack_acid_chunk,
    parse_acid_chunk,
)

CORPUS_PATH = Path(__file__).resolve().parent / "fixtures" / "acid_chunk_corpus.json"
CORPUS = json.loads(CORPUS_PATH.read_text(encoding="utf-8")) if CORPUS_PATH.exists() else None
RECORDS = CORPUS["records"] if CORPUS else []

pytestmark = pytest.mark.skipif(
    CORPUS is None,
    reason="no harvested corpus; run scripts/harvest_acid_chunks.py",
)


def _chunk(record: dict) -> AcidChunk:
    tempo = struct.unpack("<f", struct.pack("<I", record["tempo_f32_bits"]))[0]
    return AcidChunk(
        flags=record["flags"],
        root_note=record["root_note"],
        reserved_u16=record["reserved_u16"],
        reserved_f32=0.0,
        beats=record["beats"],
        meter_den=record["meter_den"],
        meter_num=record["meter_num"],
        tempo_bpm=tempo,
    )


def test_manifest_integrity() -> None:
    canonical = json.dumps(RECORDS, sort_keys=True, separators=(",", ":"))
    assert hashlib.sha256(canonical.encode("utf-8")).hexdigest() == CORPUS["records_sha256"]
    assert CORPUS["record_count"] == len(RECORDS)
    assert RECORDS, "corpus must not be empty"


def test_the_manifest_carries_no_content() -> None:
    text = CORPUS_PATH.read_text(encoding="utf-8")
    for marker in (".wav", ".WAV", "RIFF", "\\\\", "C:"):
        assert marker not in text, f"corpus leaks {marker!r}"


@pytest.mark.parametrize("record", RECORDS, ids=lambda r: r["sha256"][:12])
def test_packing_reproduces_the_bytes_that_were_on_the_disc(record: dict) -> None:
    packed = pack_acid_chunk(_chunk(record))
    assert len(packed) == ACID_CHUNK_BYTES
    assert hashlib.sha256(packed).hexdigest() == record["sha256"]
    assert parse_acid_chunk(packed) == _chunk(record)


def test_corpus_is_varied_enough_to_be_evidence() -> None:
    """All-identical records would pass the digest check and prove nothing."""
    assert len({r["tempo_f32_bits"] for r in RECORDS}) >= 5
    assert len({r["flags"] for r in RECORDS}) >= 2
    assert len({r["root_note"] for r in RECORDS}) >= 2


def test_every_observed_flag_bit_has_a_name() -> None:
    unknown = {r["flags"] for r in RECORDS if r["flags"] & ~KNOWN_FLAGS}
    assert unknown == set(), f"unrecognised acid flag bits on a real disc: {unknown}"
