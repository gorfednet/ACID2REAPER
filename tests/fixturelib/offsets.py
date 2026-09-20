"""
Byte offsets inside ``tests/fixtures/DrumRollUpDemo.acd``.

These are the offsets tests use to corrupt specific fields of the real fixture.
They were duplicated as bare literals across test modules; keeping them here
gives them a name and a single home. ``tests/test_fixture_offsets.py`` re-derives
every constant from the parser and fails if the fixture ever changes.
"""

from __future__ import annotations

# The 5c538752 cached-source leaf: chunk header, then payload, then the verbatim
# copy of the source WAV's standard ``acid`` RIFF chunk.
SOURCE_ACID_LEAF_OFFSET = 2312
SOURCE_ACID_PAYLOAD_OFFSET = SOURCE_ACID_LEAF_OFFSET + 24  # 2336
SOURCE_ACID_CHUNK_OFFSET = SOURCE_ACID_PAYLOAD_OFFSET + 8  # 2344

# Field offsets within the cached ``acid`` chunk.
SOURCE_BEATS_OFFSET = SOURCE_ACID_CHUNK_OFFSET + 12  # 2356
SOURCE_TEMPO_OFFSET = SOURCE_ACID_CHUNK_OFFSET + 20  # 2364

# The b28f2d5a project record.
PROJECT_RECORD_PAYLOAD_OFFSET = 64
