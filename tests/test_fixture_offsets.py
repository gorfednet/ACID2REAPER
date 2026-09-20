"""
Re-derive every constant in ``fixturelib.offsets`` from the parser.

The constants exist so tests can corrupt a specific field of the real fixture
without bare magic numbers. This module is what keeps them honest: if the
fixture or the Wave64 layout ever changes, the literals fail here rather than
silently corrupting the wrong bytes somewhere else.
"""

from __future__ import annotations

from pathlib import Path

from acid2reaper.binary.wave64 import (
    PROJECT_GUID,
    SOURCE_ACID_GUID,
    iter_wave64_nodes,
    parse_wave64_tree,
)
from fixturelib.offsets import (
    PROJECT_RECORD_PAYLOAD_OFFSET,
    SOURCE_ACID_CHUNK_OFFSET,
    SOURCE_ACID_LEAF_OFFSET,
    SOURCE_ACID_PAYLOAD_OFFSET,
    SOURCE_BEATS_OFFSET,
    SOURCE_TEMPO_OFFSET,
)


def test_offsets_match_the_parsed_fixture(drum_roll_bytes: bytes) -> None:
    root = parse_wave64_tree(drum_roll_bytes)
    assert root is not None

    leaf = next(
        n for n in iter_wave64_nodes(root) if n.guid == SOURCE_ACID_GUID and n.form_guid is None
    )
    assert leaf.offset == SOURCE_ACID_LEAF_OFFSET
    assert leaf.payload_offset == SOURCE_ACID_PAYLOAD_OFFSET
    # The leaf wraps an 8-byte record header around the source WAV's acid chunk.
    assert leaf.payload_offset + 8 == SOURCE_ACID_CHUNK_OFFSET
    assert SOURCE_ACID_CHUNK_OFFSET + 12 == SOURCE_BEATS_OFFSET
    assert SOURCE_ACID_CHUNK_OFFSET + 20 == SOURCE_TEMPO_OFFSET

    project = next(n for n in root.children if n.guid == PROJECT_GUID)
    assert project.payload_offset == PROJECT_RECORD_PAYLOAD_OFFSET


def test_fixture_is_the_expected_file(drum_roll_path: Path, drum_roll_bytes: bytes) -> None:
    assert drum_roll_path.name == "DrumRollUpDemo.acd"
    assert len(drum_roll_bytes) == 7800
