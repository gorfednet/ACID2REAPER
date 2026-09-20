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

from .acid_chunk import (
    ACID_CHUNK_BYTES,
    BEATS_MAX,
    FLAG_ONE_SHOT,
    METER_MAX,
    TEMPO_MAX,
    TEMPO_MIN,
    AcidChunk,
    parse_acid_chunk,
)
from .meter import DEN_NUM, resolve_meter

RIFF_GUID = uuid.UUID("66666972-912e-11cf-a5d6-28db04c10000")
LIST_GUID = uuid.UUID("7473696c-912f-11cf-a5d6-28db04c10000")
PROJECT_GUID = uuid.UUID("b28f2d5a-230f-11d2-86af-00c04f8edb8a")
TRACK_LIST_FORM_GUID = uuid.UUID("4d6c0747-2316-11d2-86b0-00c04f8edb8a")
TRACK_FORM_GUID = uuid.UUID("4d6c0748-2316-11d2-86b0-00c04f8edb8a")
EVENT_LIST_FORM_GUID = uuid.UUID("4d6c0749-2316-11d2-86b0-00c04f8edb8a")
EVENT_GUID = uuid.UUID("168d206a-2321-11d2-86b0-00c04f8edb8a")
SOURCE_ACID_GUID = uuid.UUID("5c538752-e345-4f78-83b8-551935b4c6f7")
# Newer ACID builds moved the per-track media reference out of the 4d6c0749
# track record into its own leaf. Projects from those builds have an empty
# 88-byte track record, so looking only at 4d6c0749 loses every path.
TRACK_MEDIA_GUID = uuid.UUID("bf0a0344-f8a7-47f4-88cb-a63c7756ba9e")
# The project timebase record: PPQ, tempo as microseconds per beat, and the
# time signature. This -- not the project record's float64 -- is where ACID
# keeps the tempo the user actually set.
TIMEBASE_FORM_GUID = uuid.UUID("946739be-391a-4384-8785-38bda35f409a")

# The 5c538752 leaf wraps an eight-byte record header (uint32 record byte count,
# int32 record type/version tag) around a verbatim copy of the source media
# file's standard ACID ``acid`` RIFF chunk, so the cached loop is decoded by the
# shared parser in :mod:`.acid_chunk`.
_SOURCE_ACID_RECORD_HEADER = 8


@dataclass(frozen=True)
class Wave64Node:
    """One Wave64 chunk; list chunks also expose their form and children."""

    guid: uuid.UUID
    offset: int
    size: int
    payload_offset: int
    payload_size: int
    form_guid: Optional[uuid.UUID] = None
    children: Tuple[Wave64Node, ...] = ()


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
    flags: int = 0
    root_note: Optional[int] = None

    @property
    def one_shot(self) -> bool:
        """True for a one-shot source, which must never be beat-mapped."""
        return bool(self.flags & FLAG_ONE_SHOT)


@dataclass(frozen=True)
class AcidTrackEvents:
    media_path: Optional[str]
    events: Tuple[AcidEventTicks, ...]
    source_loop: Optional[AcidSourceLoop] = None


@dataclass(frozen=True)
class AcidTimebase:
    """Project tempo, resolution and meter, from the 946739be timebase record."""

    ppq: int
    usec_per_beat: int
    tempo_bpm: float
    time_sig_num: Optional[int]
    time_sig_den: Optional[int]


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
    if root_guid != RIFF_GUID:
        return None
    if root_size < 40 or root_size > len(data):
        # Some ACID builds leave the root size at the bare header length (24)
        # instead of backfilling it after writing. The chunk stream is intact,
        # so fall back to the file extent rather than rejecting the project.
        if root_size >= 40:
            return None
        root_size = len(data)

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


def _track_media_path(
    data: bytes,
    track: Wave64Node,
    record: Optional[Wave64Node],
) -> Optional[str]:
    """
    Find a track's media file reference, across ACID build generations.

    Older builds store the UTF-16LE path inside the 4d6c0749 track record.
    Newer builds leave that record empty and put the path in a dedicated
    bf0a0344 leaf instead, which is why projects saved by different ACID
    versions used to convert with every track pointing at one fallback file.

    A track may carry several media leaves (a source replaced mid-project, or
    events drawn from more than one file). We take the first, which is the one
    ACID names the track after.
    """
    if record is not None:
        path = _first_utf16_audio_path(data[record.payload_offset : record.offset + record.size])
        if path:
            return path
    for node in iter_wave64_nodes(track):
        if node.guid != TRACK_MEDIA_GUID or node.form_guid is not None:
            continue
        path = _first_utf16_audio_path(data[node.payload_offset : node.offset + node.size])
        if path:
            return path
    return None


def _source_loop_in_track(data: bytes, track: Wave64Node) -> Optional[AcidSourceLoop]:
    """Read a track's cached source-loop metadata from its 5c538752 leaf, if plausible."""

    minimum = _SOURCE_ACID_RECORD_HEADER + ACID_CHUNK_BYTES
    for node in iter_wave64_nodes(track):
        if node.guid != SOURCE_ACID_GUID or node.form_guid is not None:
            continue
        if node.payload_size < minimum:
            continue
        try:
            record_bytes = struct.unpack_from("<I", data, node.payload_offset)[0]
        except struct.error:
            continue
        if not minimum <= record_bytes <= node.payload_size:
            continue
        chunk = parse_acid_chunk(data, node.payload_offset + _SOURCE_ACID_RECORD_HEADER)
        if chunk is None:
            continue
        return _source_loop_from_chunk(chunk)
    return None


def _source_loop_from_chunk(chunk: AcidChunk) -> AcidSourceLoop:
    """Narrow a decoded ``acid`` chunk to the fields we are willing to act on."""
    return AcidSourceLoop(
        tempo_bpm=chunk.tempo_bpm,
        beats=chunk.beats if 1 <= chunk.beats <= BEATS_MAX else None,
        time_sig_num=chunk.meter_num if 1 <= chunk.meter_num <= METER_MAX else None,
        time_sig_den=chunk.meter_den if 1 <= chunk.meter_den <= METER_MAX else None,
        flags=chunk.flags,
        root_note=chunk.effective_root_note,
    )


#: Positions and lengths beyond this are a bad decode, not a long song: even at
#: the slowest tempo we accept, this is well over a day of audio.
MAX_EVENT_TICKS = 24 * 60 * 400 * 24576

_TIMEBASE_RECORD_BYTES = 20
_TIMEBASE_PPQ = 4
_TIMEBASE_USEC_PER_BEAT = 8
_TIMEBASE_METER = 16


def tempo_from_usec_per_beat(usec_per_beat: int) -> float:
    """
    Recover the authored tempo from ACID's integer microseconds-per-beat.

    The stored value is rounded, so dividing straight back gives 177.99982
    where the user typed 178. Rather than leave that in the REAPER tempo box,
    look for the simplest decimal that re-encodes to exactly the same integer.
    If none does, return the plain quotient.
    """
    exact = 60_000_000.0 / usec_per_beat
    for places in (0, 1, 2, 3):
        candidate = round(exact, places)
        if candidate > 0 and round(60_000_000.0 / candidate) == usec_per_beat:
            return candidate
    return exact


def extract_timebase(data: bytes, root: Wave64Node, *, meter_order: str = DEN_NUM) -> Optional[AcidTimebase]:
    """Decode the 946739be timebase record, if the project carries one."""
    container = next(
        (n for n in iter_wave64_nodes(root) if n.form_guid == TIMEBASE_FORM_GUID),
        None,
    )
    if container is None:
        return None
    for leaf in container.children:
        if leaf.form_guid is not None or leaf.payload_size < 24:
            continue
        try:
            record_bytes = struct.unpack_from("<I", data, leaf.payload_offset)[0]
            ppq = struct.unpack_from("<I", data, leaf.payload_offset + _TIMEBASE_PPQ)[0]
            usec = struct.unpack_from("<I", data, leaf.payload_offset + _TIMEBASE_USEC_PER_BEAT)[0]
            meter_a, meter_b = struct.unpack_from("<HH", data, leaf.payload_offset + _TIMEBASE_METER)
        except struct.error:
            continue
        if record_bytes != _TIMEBASE_RECORD_BYTES:
            continue
        if not 1 <= ppq <= 10_000_000 or usec <= 0:
            continue
        tempo = tempo_from_usec_per_beat(usec)
        if not math.isfinite(tempo) or not TEMPO_MIN <= tempo <= TEMPO_MAX:
            continue
        # ACID 3-era builds leave this pair zeroed and keep the meter in the
        # project record instead, so an unusable pair is normal, not a failure.
        meter = resolve_meter(meter_a, meter_b, order=meter_order)
        return AcidTimebase(
            ppq=ppq,
            usec_per_beat=usec,
            tempo_bpm=tempo,
            time_sig_num=meter[0] if meter else None,
            time_sig_den=meter[1] if meter else None,
        )
    return None


def extract_acid_wave64_timeline(
    data: bytes,
    *,
    meter_order: str = DEN_NUM,
) -> Optional[AcidWave64Timeline]:
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
        meter_a, meter_b = struct.unpack_from("<HH", data, payload + 40)
        ppq = struct.unpack_from("<I", data, payload + 44)[0]
    except struct.error:
        return None
    project_meter = resolve_meter(meter_a, meter_b, order=meter_order)
    time_num = project_meter[0] if project_meter else None
    time_den = project_meter[1] if project_meter else None

    # The project record's float64 is a template default -- it reads exactly
    # 120.0 in every real project examined, including ones authored at 98, 145
    # and 184 BPM. The timebase record is the authoritative source; fall back to
    # the project record only when a file has no timebase leaf at all.
    timebase = extract_timebase(data, root, meter_order=meter_order)
    if timebase is not None:
        tempo = timebase.tempo_bpm
        ppq = timebase.ppq
        if timebase.time_sig_num and timebase.time_sig_den:
            time_num = timebase.time_sig_num
            time_den = timebase.time_sig_den

    if not math.isfinite(tempo) or not TEMPO_MIN <= tempo <= TEMPO_MAX:
        return None
    if not 1 <= ppq <= 10_000_000:
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
        media_path = _track_media_path(data, track, record)

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
                # Signed, not unsigned. An event dragged left of bar 1 is stored
                # as a negative position; reading it as uint64 turned -41026
                # ticks into 1.8e19 and put the clip 10 million years in.
                position, length = struct.unpack_from("<qq", data, node.payload_offset + 0x10)
                if length <= 0 or length > MAX_EVENT_TICKS:
                    continue
                if position > MAX_EVENT_TICKS or position < -MAX_EVENT_TICKS:
                    continue
                events.append(AcidEventTicks(position, length))
        # Keep tracks with no events. Dropping them silently renumbered every
        # track after the gap, and made an otherwise-valid empty project look
        # like an undecodable file.
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
