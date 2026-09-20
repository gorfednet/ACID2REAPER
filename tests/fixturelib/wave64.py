"""
Write Wave64-shell ACID project files for tests.

The one real project available is 4/4 at 120 BPM with a single track, so every
other meter, tempo and track layout has to be synthesised. This builder emits
the same chunk graph the real file uses, with the decoded fields parameterised.

It shares the parser's offset table, so "build X then parse X" proves nothing
about the offsets themselves. What anchors it is
``tests/test_fixture_builder_anchor.py``: the builder must reproduce the real
fixture's decoded timeline and its leaf payload bytes exactly. If an offset were
wrong, the bytes it writes would differ from the bytes in the real file.

The undecoded leaves of a real project (stretch markers, per-track mixer
records) are deliberately omitted rather than copied in verbatim. Embedding them
would make the builder a transcription of one file and hide layout errors behind
an opaque byte table.
"""

from __future__ import annotations

import struct
import uuid
from dataclasses import dataclass, field
from typing import Mapping, Optional, Sequence, Tuple

from acid2reaper.binary.acid_chunk import AcidChunk, pack_acid_chunk
from acid2reaper.binary.wave64 import (
    EVENT_GUID,
    EVENT_LIST_FORM_GUID,
    LIST_GUID,
    PROJECT_GUID,
    RIFF_GUID,
    SOURCE_ACID_GUID,
    TIMEBASE_FORM_GUID,
    TRACK_FORM_GUID,
    TRACK_LIST_FORM_GUID,
    TRACK_MEDIA_GUID,
)

ACID_PROJECT_FORM_GUID = uuid.UUID("ea1c076d-efa3-4c78-9057-7f79ee252aae")

_WAVE64_HEADER = 24

# Record type/version tags, read from the real fixture. The second word of a
# leaf record header is not "reserved 0"; it differs per record type.
_PROJECT_RECORD_TAG = 0x00010001
_TRACK_RECORD_TAG = -98
_EVENT_RECORD_TAG = -100
_SOURCE_ACID_TAG = 0
_TIMEBASE_PPQ_WORD = 24576

# The project record's 96 fixed bytes, transcribed from the real fixture. Only
# the named fields below are patched; the rest are undecoded and kept verbatim
# so the anchor test can compare bytes.
_PROJECT_RECORD_TEMPLATE = bytes.fromhex(
    "60000000010001000100000044ac0000"
    "000000000000f03f0000000000005e40"
    "00000000000000000400040000600000"
    "0000000000000000cc0000005c000000"
    "00000000000000000100000000000000"
    "000000000000000000000c0000000000"
)
_TRACK_RECORD_TEMPLATE = bytes.fromhex(
    "400000009effffff100020002e000000"
    "02000000000000000000000002000000"
    "28000000200000000000000000000000"
    "de680601000000000200000000000000"
)
# The real track record ends with eight zero bytes after its two strings --
# further empty strings, by the look of it. Kept so the anchor can compare bytes.
_TRACK_RECORD_TRAILER = b"\x00" * 8
_EVENT_RECORD_TEMPLATE = bytes.fromhex(
    "480000009cffffff0000000000000000"
    "00000000000000000080010000000000"
    "00000000000000000000000000000000"
    "000000000000f03f0000000000000000"
    "00000000000000002800000000000000"
    "00000000000000000000000000000000"
    "0000803f0300000002000000feffffff"
)

# Field offsets inside the project record payload.
_PROJECT_SAMPLE_RATE = 12
_PROJECT_TEMPO_F64 = 24
_PROJECT_METER = 40
_PROJECT_PPQ = 44

# Field offsets inside an event record payload.
_EVENT_POSITION = 0x10
_EVENT_LENGTH = 0x18
#: An undecoded uint16 that is 0 on a track's first event and 492 on the rest in
#: the real fixture -- an automatic crossfade length, most likely. We do not
#: interpret it; the spec carries it so the anchor can compare bytes exactly.
_EVENT_TAIL_WORD = 88

MEDIA_IN_TRACK_RECORD = "track-record"
MEDIA_IN_DEDICATED_LEAF = "media-leaf"


@dataclass(frozen=True)
class EventSpec:
    position_ticks: int
    length_ticks: int
    #: Undecoded trailing word; see ``_EVENT_TAIL_WORD``.
    tail_word: int = 0


@dataclass(frozen=True)
class TrackSpec:
    media_filename: str
    display_name: Optional[str] = None
    events: Tuple[EventSpec, ...] = ()
    source_acid: Optional[AcidChunk] = None

    @property
    def name(self) -> str:
        return self.display_name if self.display_name is not None else self.media_filename.rsplit(".", 1)[0]


@dataclass(frozen=True)
class ProjectSpec:
    tempo_bpm: float = 120.0
    sample_rate_hz: int = 44100
    ppq: int = 24576
    meter_num: int = 4
    meter_den: int = 4
    #: Where the per-track media reference goes. Older ACID builds put it in the
    #: track record; newer ones use a dedicated leaf and leave the record empty.
    media_layout: str = MEDIA_IN_TRACK_RECORD
    #: Emit the meter in the timebase record too. ACID 3-era files zero it there.
    meter_in_timebase: bool = False
    project_path: str = "C:\\ACID\\Untitled.acd"
    app_dir: str = "C:\\ACID\\"
    tracks: Tuple[TrackSpec, ...] = ()


def _pad8(data: bytes) -> bytes:
    return data + b"\x00" * ((-len(data)) % 8)


def _chunk(guid: uuid.UUID, payload: bytes) -> bytes:
    """
    One Wave64 chunk.

    The payload is padded to an eight-byte boundary *before* the size is
    computed, which is why every chunk size in a real ACID file is a multiple
    of eight.
    """
    payload = _pad8(payload)
    return guid.bytes_le + struct.pack("<Q", _WAVE64_HEADER + len(payload)) + payload


def _list(form: uuid.UUID, children: Sequence[bytes]) -> bytes:
    return _chunk(LIST_GUID, form.bytes_le + b"".join(children))


def _record(tag: int, body: bytes) -> bytes:
    return struct.pack("<Ii", 8 + len(body), tag) + body


def _utf16z(text: str) -> bytes:
    return text.encode("utf-16-le") + b"\x00\x00"


def _project_record(spec: ProjectSpec) -> bytes:
    body = bytearray(_PROJECT_RECORD_TEMPLATE)
    struct.pack_into("<I", body, _PROJECT_SAMPLE_RATE, spec.sample_rate_hz)
    struct.pack_into("<d", body, _PROJECT_TEMPO_F64, spec.tempo_bpm)
    struct.pack_into("<HH", body, _PROJECT_METER, spec.meter_den, spec.meter_num)
    struct.pack_into("<I", body, _PROJECT_PPQ, spec.ppq)
    tail = _utf16z(spec.project_path) + _utf16z(spec.app_dir)
    return _chunk(PROJECT_GUID, bytes(body) + tail)


def _timebase(spec: ProjectSpec) -> bytes:
    usec_per_beat = round(60_000_000.0 / spec.tempo_bpm)
    meter = (spec.meter_den, spec.meter_num) if spec.meter_in_timebase else (0, 0)
    payload = struct.pack(
        "<IIIIHHI",
        20,
        _TIMEBASE_PPQ_WORD if spec.ppq == 24576 else spec.ppq,
        usec_per_beat,
        57,
        meter[0],
        meter[1],
        0,
    )
    return _list(TIMEBASE_FORM_GUID, [_chunk(TIMEBASE_FORM_GUID, payload)])


def _track_record(track: TrackSpec, layout: str) -> bytes:
    body = bytes(_TRACK_RECORD_TEMPLATE)
    if layout == MEDIA_IN_TRACK_RECORD:
        tail = _utf16z(track.media_filename) + _utf16z(track.name)
    else:
        # Newer builds leave the record without a path; it lives in its own leaf.
        tail = _utf16z(track.name)
    return _chunk(EVENT_LIST_FORM_GUID, body + tail + _TRACK_RECORD_TRAILER)


def _media_leaf(track: TrackSpec) -> bytes:
    payload = _record(1, struct.pack("<III", 1, 0, len(_utf16z(track.media_filename))))
    return _list(TRACK_MEDIA_GUID, [_chunk(TRACK_MEDIA_GUID, payload + _utf16z(track.media_filename))])


def _event(event: EventSpec) -> bytes:
    body = bytearray(_EVENT_RECORD_TEMPLATE)
    struct.pack_into("<Q", body, _EVENT_POSITION, event.position_ticks)
    struct.pack_into("<Q", body, _EVENT_LENGTH, event.length_ticks)
    struct.pack_into("<H", body, _EVENT_TAIL_WORD, event.tail_word)
    return _chunk(EVENT_GUID, bytes(body))


def _source_acid_leaf(chunk: AcidChunk) -> bytes:
    payload = _record(_SOURCE_ACID_TAG, pack_acid_chunk(chunk))
    return _list(SOURCE_ACID_GUID, [_chunk(SOURCE_ACID_GUID, payload)])


def _track(track: TrackSpec, layout: str) -> bytes:
    children = [_track_record(track, layout)]
    if layout == MEDIA_IN_DEDICATED_LEAF:
        children.append(_media_leaf(track))
    if track.source_acid is not None:
        children.append(_source_acid_leaf(track.source_acid))
    children.append(_list(EVENT_LIST_FORM_GUID, [_event(e) for e in track.events]))
    return _list(TRACK_FORM_GUID, children)


def build_acd(spec: ProjectSpec) -> bytes:
    """Serialise a whole ACID project shell."""
    children = [
        _project_record(spec),
        _list(TRACK_LIST_FORM_GUID, [_track(t, spec.media_layout) for t in spec.tracks]),
        _timebase(spec),
    ]
    body = ACID_PROJECT_FORM_GUID.bytes_le + b"".join(children)
    return RIFF_GUID.bytes_le + struct.pack("<Q", _WAVE64_HEADER + len(body)) + body


def build_acd_zip(
    spec: ProjectSpec,
    media: Mapping[str, bytes],
    *,
    inner_name: str = "project.acd",
) -> bytes:
    """Package a project plus its media the way ACID's ACD-ZIP container does."""
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(inner_name, build_acd(spec))
        for name, blob in media.items():
            archive.writestr(name, blob)
    return buffer.getvalue()
