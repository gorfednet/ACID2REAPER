"""
Sony Wave64-style GUID chunk parsing for catalogued ACID projects.

Chunk roles and byte offsets are catalogued in ``data/acd_signatures.json``
under ``wave64_layout``. They were derived from a single real project file, so
non-4/4 time-signature field order and multi-track layouts are unverified: see
the limitations section in the README before trusting or extending them. Fields
that cannot be confirmed are gated on plausibility checks and fall back to
neutral defaults rather than being guessed.
"""

from __future__ import annotations

import math
import struct
import uuid
from dataclasses import dataclass
from typing import Iterator, Optional, Tuple


RIFF_GUID = uuid.UUID("66666972-912e-11cf-a5d6-28db04c10000")
LIST_GUID = uuid.UUID("7473696c-912f-11cf-a5d6-28db04c10000")
PROJECT_GUID = uuid.UUID("b28f2d5a-230f-11d2-86af-00c04f8edb8a")
TRACK_LIST_FORM_GUID = uuid.UUID("4d6c0747-2316-11d2-86b0-00c04f8edb8a")
TRACK_FORM_GUID = uuid.UUID("4d6c0748-2316-11d2-86b0-00c04f8edb8a")
EVENT_LIST_FORM_GUID = uuid.UUID("4d6c0749-2316-11d2-86b0-00c04f8edb8a")
EVENT_GUID = uuid.UUID("168d206a-2321-11d2-86b0-00c04f8edb8a")
SOURCE_ACID_GUID = uuid.UUID("5c538752-e345-4f78-83b8-551935b4c6f7")

# The 5c538752 leaf wraps an eight-byte record header (uint32 record byte count,
# uint32 reserved) around a verbatim copy of the source media file's standard
# ACID ``acid`` RIFF chunk, so the cached loop fields keep that chunk's offsets.
_SOURCE_ACID_RECORD_HEADER = 8
_SOURCE_ACID_CHUNK_BYTES = 24
_ACID_CHUNK_BEATS = 12
_ACID_CHUNK_METER_DEN = 16
_ACID_CHUNK_METER_NUM = 18
_ACID_CHUNK_TEMPO = 20


@dataclass(frozen=True)
class Wave64Node:
    """One Wave64 chunk; list chunks also expose their form and children."""

    guid: uuid.UUID
    offset: int
    size: int
    payload_offset: int
    payload_size: int
    form_guid: Optional[uuid.UUID] = None
    children: Tuple["Wave64Node", ...] = ()


@dataclass(frozen=True)
class AcidEventTicks:
    position_ticks: int
    length_ticks: int


@dataclass(frozen=True)
class AcidSourceLoop:
    """Loop metadata ACID cached from the source media file's own ``acid`` chunk."""

    tempo_bpm: float
    beats: Optional[int]
    time_sig_num: Optional[int]
    time_sig_den: Optional[int]


@dataclass(frozen=True)
class AcidTrackEvents:
    media_path: Optional[str]
    events: Tuple[AcidEventTicks, ...]
    source_loop: Optional[AcidSourceLoop] = None


@dataclass(frozen=True)
class AcidWave64Timeline:
    ppq: int
    tempo_bpm: float
    sample_rate_hz: Optional[int]
    time_sig_num: Optional[int]
    time_sig_den: Optional[int]
    tracks: Tuple[AcidTrackEvents, ...]


def _align8(value: int) -> int:
    return (value + 7) & ~7


def _guid_at(data: bytes, offset: int) -> uuid.UUID:
    return uuid.UUID(bytes_le=data[offset : offset + 16])


def parse_wave64_tree(data: bytes) -> Optional[Wave64Node]:
    """
    Parse a Wave64 GUID tree.

    Chunk sizes are little-endian uint64 values that include the 24-byte
    GUID/size header. Children are aligned to eight-byte boundaries.
    """

    if len(data) < 40:
        return None
    try:
        root_guid = _guid_at(data, 0)
        root_size = struct.unpack_from("<Q", data, 16)[0]
        root_form = _guid_at(data, 24)
    except (ValueError, struct.error):
        return None
    if root_guid != RIFF_GUID or root_size < 40 or root_size > len(data):
        return None

    chunk_budget = max(1, root_size // 24)

    def parse_children(start: int, end: int, depth: int) -> Optional[Tuple[Wave64Node, ...]]:
        nonlocal chunk_budget
        if depth > 64:
            return None
        nodes = []
        offset = start
        while offset < end:
            if end - offset < 24:
                if any(data[offset:end]):
                    return None
                break
            if chunk_budget <= 0:
                return None
            chunk_budget -= 1
            try:
                guid = _guid_at(data, offset)
                size = struct.unpack_from("<Q", data, offset + 16)[0]
            except (ValueError, struct.error):
                return None
            if size < 24 or offset + size > end:
                return None

            payload_offset = offset + 24
            payload_size = size - 24
            form_guid = None
            children: Tuple[Wave64Node, ...] = ()
            if guid == LIST_GUID:
                if size < 40:
                    return None
                form_guid = _guid_at(data, payload_offset)
                parsed = parse_children(payload_offset + 16, offset + size, depth + 1)
                if parsed is None:
                    return None
                children = parsed

            nodes.append(
                Wave64Node(
                    guid=guid,
                    offset=offset,
                    size=size,
                    payload_offset=payload_offset,
                    payload_size=payload_size,
                    form_guid=form_guid,
                    children=children,
                )
            )
            offset += _align8(size)
            if offset > end:
                return None
        return tuple(nodes)

    children = parse_children(40, root_size, 0)
    if children is None:
        return None
    return Wave64Node(
        guid=root_guid,
        offset=0,
        size=root_size,
        payload_offset=24,
        payload_size=root_size - 24,
        form_guid=root_form,
        children=children,
    )


def iter_wave64_nodes(node: Wave64Node) -> Iterator[Wave64Node]:
    """Yield a tree in pre-order."""

    yield node
    for child in node.children:
        yield from iter_wave64_nodes(child)


def _first_utf16_audio_path(data: bytes) -> Optional[str]:
    extensions = (".wav", ".wave", ".aif", ".aiff", ".mp3", ".flac", ".ogg", ".wma")
    best: Optional[str] = None
    for parity in (0, 1):
        start = parity
        while start + 2 <= len(data):
            end = start
            chars = []
            while end + 2 <= len(data):
                code = struct.unpack_from("<H", data, end)[0]
                if code == 0 or code < 0x20 or code > 0x7E:
                    break
                chars.append(chr(code))
                end += 2
            if len(chars) >= 4:
                value = "".join(chars)
                if value.lower().endswith(extensions):
                    if best is None or len(value) < len(best):
                        best = value
            start = end + 2 if end > start else start + 2
    return best


def _source_loop_in_track(data: bytes, track: Wave64Node) -> Optional[AcidSourceLoop]:
    """Read a track's cached source-loop tempo from its 5c538752 leaf, if plausible."""

    minimum = _SOURCE_ACID_RECORD_HEADER + _SOURCE_ACID_CHUNK_BYTES
    for node in iter_wave64_nodes(track):
        if node.guid != SOURCE_ACID_GUID or node.form_guid is not None:
            continue
        if node.payload_size < minimum:
            continue
        acid = node.payload_offset + _SOURCE_ACID_RECORD_HEADER
        try:
            record_bytes = struct.unpack_from("<I", data, node.payload_offset)[0]
            beats = struct.unpack_from("<I", data, acid + _ACID_CHUNK_BEATS)[0]
            sig_den = struct.unpack_from("<H", data, acid + _ACID_CHUNK_METER_DEN)[0]
            sig_num = struct.unpack_from("<H", data, acid + _ACID_CHUNK_METER_NUM)[0]
            tempo = struct.unpack_from("<f", data, acid + _ACID_CHUNK_TEMPO)[0]
        except struct.error:
            continue
        if not minimum <= record_bytes <= node.payload_size:
            continue
        if not math.isfinite(tempo) or not 20.0 <= tempo <= 400.0:
            continue
        return AcidSourceLoop(
            tempo_bpm=float(tempo),
            beats=beats if 1 <= beats <= 1_000_000 else None,
            time_sig_num=sig_num if 1 <= sig_num <= 32 else None,
            time_sig_den=sig_den if 1 <= sig_den <= 32 else None,
        )
    return None


def extract_acid_wave64_timeline(data: bytes) -> Optional[AcidWave64Timeline]:
    """Extract verified project timing and event leaves from the ACID Wave64 layout."""

    root = parse_wave64_tree(data)
    if root is None:
        return None

    project = next((n for n in root.children if n.guid == PROJECT_GUID), None)
    if project is None or project.payload_size < 48:
        return None
    payload = project.payload_offset
    try:
        sample_rate = struct.unpack_from("<I", data, payload + 12)[0]
        tempo = struct.unpack_from("<d", data, payload + 24)[0]
        time_num = struct.unpack_from("<I", data, payload + 36)[0]
        time_den = struct.unpack_from("<I", data, payload + 40)[0]
        ppq = struct.unpack_from("<I", data, payload + 44)[0]
    except struct.error:
        return None
    if not math.isfinite(tempo) or not 20.0 <= tempo <= 400.0 or not 1 <= ppq <= 10_000_000:
        return None
    if sample_rate not in {
        8000,
        11025,
        12000,
        16000,
        22050,
        24000,
        32000,
        44100,
        48000,
        88200,
        96000,
        176400,
        192000,
    }:
        sample_rate = None
    if not 1 <= time_num <= 32:
        time_num = None
    if not 1 <= time_den <= 32:
        time_den = None

    track_list = next(
        (n for n in iter_wave64_nodes(root) if n.form_guid == TRACK_LIST_FORM_GUID),
        None,
    )
    if track_list is None:
        return None

    tracks = []
    for track in (n for n in track_list.children if n.form_guid == TRACK_FORM_GUID):
        record = next(
            (
                n
                for n in track.children
                if n.guid == EVENT_LIST_FORM_GUID and n.form_guid is None
            ),
            None,
        )
        media_path = None
        if record is not None:
            media_path = _first_utf16_audio_path(
                data[record.payload_offset : record.offset + record.size]
            )

        event_list = next(
            (n for n in track.children if n.form_guid == EVENT_LIST_FORM_GUID),
            None,
        )
        events = []
        if event_list is not None:
            for node in iter_wave64_nodes(event_list):
                if node.guid != EVENT_GUID or node.form_guid is not None:
                    continue
                if node.payload_size < 32:
                    continue
                position, length = struct.unpack_from("<QQ", data, node.payload_offset + 0x10)
                if length > 0:
                    events.append(AcidEventTicks(position, length))
        if events:
            tracks.append(
                AcidTrackEvents(
                    media_path=media_path,
                    events=tuple(events),
                    source_loop=_source_loop_in_track(data, track),
                )
            )

    if not tracks:
        return None
    return AcidWave64Timeline(
        ppq=ppq,
        tempo_bpm=float(tempo),
        sample_rate_hz=sample_rate,
        time_sig_num=time_num,
        time_sig_den=time_den,
        tracks=tuple(tracks),
    )
