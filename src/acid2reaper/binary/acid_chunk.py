"""
The standard ACID ``acid`` RIFF chunk.

Unlike the ``.acd`` project format, this 24-byte chunk is publicly documented
and appears verbatim in two places we care about: inside ACIDized source WAVs,
and cached inside a project's ``5c538752`` leaf (see :mod:`.wave64`). Both use
the same offsets, so they share this one decoder.

The layout below is byte-verified against ``tests/fixtures/samples/Break
Pattern c.WAV``::

    00 00 00 00  3c 00  00 80  00 00 00 00  04 00 00 00  04 00  04 00  95 8e 0b 43
    |flags     | |root| |rsv | |reserved  | |beats     | |den | |num | |tempo    |
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from typing import Optional

ACID_CHUNK_BYTES = 24

# Flag bits. Only ONE_SHOT is acted on; see the note on STRETCH below.
FLAG_ONE_SHOT = 0x01
FLAG_ROOT_NOTE_SET = 0x02
FLAG_STRETCH = 0x04
FLAG_DISK_BASED = 0x08
FLAG_ACIDIZER = 0x10
KNOWN_FLAGS = 0x1F

OFF_FLAGS = 0
OFF_ROOT_NOTE = 4
OFF_RESERVED_U16 = 6
OFF_RESERVED_F32 = 8
OFF_BEATS = 12
OFF_METER_DEN = 16
OFF_METER_NUM = 18
OFF_TEMPO = 20

# Plausibility gates. A chunk outside these is a bad decode, not a strange loop.
TEMPO_MIN = 20.0
TEMPO_MAX = 400.0
BEATS_MAX = 1_000_000
METER_MAX = 32


@dataclass(frozen=True)
class AcidChunk:
    """Decoded ``acid`` chunk contents."""

    flags: int = 0
    root_note: int = 0x3C
    reserved_u16: int = 0x8000
    reserved_f32: float = 0.0
    beats: int = 4
    meter_den: int = 4
    meter_num: int = 4
    tempo_bpm: float = 120.0

    @property
    def one_shot(self) -> bool:
        """
        True when the source is a one-shot rather than a loop.

        This is the only flag bit worth acting on. In particular ``FLAG_STRETCH``
        is *not* a usable "do beat-map this" signal: the ACID 3 fixture has
        ``flags == 0`` yet ACID demonstrably beat-maps that loop, so the bit
        being clear tells us nothing.
        """
        return bool(self.flags & FLAG_ONE_SHOT)

    @property
    def root_note_set(self) -> bool:
        return bool(self.flags & FLAG_ROOT_NOTE_SET)

    @property
    def set_by_acidizer(self) -> bool:
        return bool(self.flags & FLAG_ACIDIZER)

    @property
    def effective_root_note(self) -> Optional[int]:
        """
        The root note, or ``None`` when the file does not actually carry one.

        The fixture stores ``root_note == 0x3C`` with ``flags == 0``, so the
        value is a default rather than a real root. Only trust it when the
        root-note bit is set.
        """
        return self.root_note if self.root_note_set else None


def parse_acid_chunk(data: bytes, offset: int = 0) -> Optional[AcidChunk]:
    """Decode a 24-byte ``acid`` chunk payload, or ``None`` if it is implausible."""
    if offset < 0 or len(data) - offset < ACID_CHUNK_BYTES:
        return None
    try:
        flags = struct.unpack_from("<I", data, offset + OFF_FLAGS)[0]
        root_note = struct.unpack_from("<H", data, offset + OFF_ROOT_NOTE)[0]
        reserved_u16 = struct.unpack_from("<H", data, offset + OFF_RESERVED_U16)[0]
        reserved_f32 = struct.unpack_from("<f", data, offset + OFF_RESERVED_F32)[0]
        beats = struct.unpack_from("<I", data, offset + OFF_BEATS)[0]
        meter_den = struct.unpack_from("<H", data, offset + OFF_METER_DEN)[0]
        meter_num = struct.unpack_from("<H", data, offset + OFF_METER_NUM)[0]
        tempo = struct.unpack_from("<f", data, offset + OFF_TEMPO)[0]
    except struct.error:
        return None

    if not math.isfinite(tempo) or not TEMPO_MIN <= tempo <= TEMPO_MAX:
        return None

    return AcidChunk(
        flags=flags,
        root_note=root_note,
        reserved_u16=reserved_u16,
        reserved_f32=reserved_f32 if math.isfinite(reserved_f32) else 0.0,
        beats=beats,
        meter_den=meter_den,
        meter_num=meter_num,
        tempo_bpm=float(tempo),
    )


def pack_acid_chunk(chunk: AcidChunk) -> bytes:
    """
    Encode an :class:`AcidChunk` back to its 24 bytes.

    The exact inverse of :func:`parse_acid_chunk`. This ships rather than living
    in the test tree because it is what lets ``tests/test_acid_chunk_corpus.py``
    check our offsets against the digests of real chunks found on a Sonic
    Foundry loop disc -- a check that proves nothing if the packer is a
    test-local reimplementation of the same assumptions.
    """
    out = bytearray(ACID_CHUNK_BYTES)
    struct.pack_into("<I", out, OFF_FLAGS, chunk.flags & 0xFFFFFFFF)
    struct.pack_into("<H", out, OFF_ROOT_NOTE, chunk.root_note & 0xFFFF)
    struct.pack_into("<H", out, OFF_RESERVED_U16, chunk.reserved_u16 & 0xFFFF)
    struct.pack_into("<f", out, OFF_RESERVED_F32, chunk.reserved_f32)
    struct.pack_into("<I", out, OFF_BEATS, chunk.beats & 0xFFFFFFFF)
    struct.pack_into("<H", out, OFF_METER_DEN, chunk.meter_den & 0xFFFF)
    struct.pack_into("<H", out, OFF_METER_NUM, chunk.meter_num & 0xFFFF)
    struct.pack_into("<f", out, OFF_TEMPO, chunk.tempo_bpm)
    return bytes(out)


def find_acid_chunk_in_riff(data: bytes) -> Optional[AcidChunk]:
    """Walk a RIFF/WAVE file's top-level chunks and decode its ``acid`` chunk."""
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return None
    offset = 12
    while offset + 8 <= len(data):
        chunk_id = data[offset : offset + 4]
        try:
            size = struct.unpack_from("<I", data, offset + 4)[0]
        except struct.error:
            return None
        body = offset + 8
        if chunk_id == b"acid":
            return parse_acid_chunk(data, body)
        offset = body + size + (size & 1)
    return None
