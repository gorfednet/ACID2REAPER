"""
Anchor the synthetic fixture builder to the one real ACID project.

The builder imports the parser's offset table, so round-tripping through it
proves nothing about whether those offsets are right. These tests supply the
missing half: the builder must produce the same bytes the real file contains,
field for field, and decode to an identical timeline. If an offset were wrong,
the value would land somewhere the real file does not have it and these fail.
"""

from __future__ import annotations

from typing import List

import pytest

from acid2reaper.binary.wave64 import (
    EVENT_GUID,
    EVENT_LIST_FORM_GUID,
    PROJECT_GUID,
    SOURCE_ACID_GUID,
    TIMEBASE_FORM_GUID,
    extract_acid_wave64_timeline,
    extract_timebase,
    iter_wave64_nodes,
    parse_wave64_tree,
)
from fixturelib.reference import DRUM_ROLL_UP_DEMO
from fixturelib.wave64 import build_acd


def _leaf_payloads(data: bytes, guid) -> List[bytes]:
    root = parse_wave64_tree(data)
    assert root is not None
    return [
        data[n.payload_offset : n.payload_offset + n.payload_size]
        for n in iter_wave64_nodes(root)
        if n.guid == guid and n.form_guid is None
    ]


@pytest.fixture(scope="module")
def built() -> bytes:
    return build_acd(DRUM_ROLL_UP_DEMO)


def test_project_record_bytes_match_the_real_file(built: bytes, drum_roll_bytes: bytes) -> None:
    assert _leaf_payloads(built, PROJECT_GUID) == _leaf_payloads(drum_roll_bytes, PROJECT_GUID)


def test_cached_acid_chunk_bytes_match_the_real_file(built: bytes, drum_roll_bytes: bytes) -> None:
    assert _leaf_payloads(built, SOURCE_ACID_GUID) == _leaf_payloads(
        drum_roll_bytes, SOURCE_ACID_GUID
    )


def test_event_record_bytes_match_the_real_file(built: bytes, drum_roll_bytes: bytes) -> None:
    ours = _leaf_payloads(built, EVENT_GUID)
    theirs = _leaf_payloads(drum_roll_bytes, EVENT_GUID)
    assert len(ours) == len(theirs) == 15
    assert ours == theirs


def test_track_record_bytes_match_the_real_file(built: bytes, drum_roll_bytes: bytes) -> None:
    """The 4d6c0749 leaf carries the media path and the track's display name."""
    ours = _leaf_payloads(built, EVENT_LIST_FORM_GUID)
    theirs = _leaf_payloads(drum_roll_bytes, EVENT_LIST_FORM_GUID)
    assert ours == theirs


def test_timebase_record_bytes_match_the_real_file(built: bytes, drum_roll_bytes: bytes) -> None:
    assert _leaf_payloads(built, TIMEBASE_FORM_GUID) == _leaf_payloads(
        drum_roll_bytes, TIMEBASE_FORM_GUID
    )


def test_decoded_timeline_is_identical(built: bytes, drum_roll_bytes: bytes) -> None:
    """
    The strongest single assertion here.

    Every dataclass in the timeline is frozen, so this compares PPQ, tempo,
    sample rate, meter, per-track media path, every event tick pair and the
    cached source loop in one go.
    """
    assert extract_acid_wave64_timeline(built) == extract_acid_wave64_timeline(drum_roll_bytes)


def test_timebase_is_identical(built: bytes, drum_roll_bytes: bytes) -> None:
    assert extract_timebase(built, parse_wave64_tree(built)) == extract_timebase(
        drum_roll_bytes, parse_wave64_tree(drum_roll_bytes)
    )


def test_every_chunk_the_builder_writes_is_eight_byte_aligned(built: bytes) -> None:
    """Real ACID files are wholly 8-aligned; a builder that is not would mask bugs."""
    root = parse_wave64_tree(built)
    for node in iter_wave64_nodes(root):
        assert node.size % 8 == 0, f"{node.guid} size {node.size}"
        assert node.offset % 8 == 0, f"{node.guid} offset {node.offset}"


def test_anchor_would_notice_a_wrong_offset(drum_roll_bytes: bytes) -> None:
    """
    Guard the guard: corrupting a decoded field must break byte equality.

    Without this, a builder that silently ignored its inputs would still pass
    every assertion above.
    """
    from dataclasses import replace

    wrong = build_acd(replace(DRUM_ROLL_UP_DEMO, sample_rate_hz=48000))
    assert _leaf_payloads(wrong, PROJECT_GUID) != _leaf_payloads(drum_roll_bytes, PROJECT_GUID)
