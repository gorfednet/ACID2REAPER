"""Write ACIDized WAV files for tests."""

from __future__ import annotations

import struct

from acid2reaper.binary.acid_chunk import AcidChunk, pack_acid_chunk


def _riff_chunk(chunk_id: bytes, body: bytes) -> bytes:
    """One RIFF chunk, padded to an even length as the format requires."""
    return chunk_id + struct.pack("<I", len(body)) + body + (b"\x00" if len(body) & 1 else b"")


def build_acidized_wav(
    *,
    acid: AcidChunk,
    sample_rate: int = 44100,
    channels: int = 2,
    bits: int = 16,
    frames: int | None = None,
) -> bytes:
    """
    Build a silent WAV carrying a real ``acid`` chunk.

    When ``frames`` is not given the audio length is derived from the chunk's
    own beats and tempo, so the file's true duration agrees with the metadata it
    advertises. Tests that compare a decoded event length against the media's
    real duration depend on that.

    Chunk order matches the real ACID fixture: ``fmt``, ``data``, then ``acid``.
    """
    if frames is None:
        frames = max(1, round(acid.beats * 60.0 / acid.tempo_bpm * sample_rate))

    block_align = channels * bits // 8
    fmt = struct.pack(
        "<HHIIHH",
        1,  # PCM
        channels,
        sample_rate,
        sample_rate * block_align,
        block_align,
        bits,
    )
    body = (
        b"WAVE"
        + _riff_chunk(b"fmt ", fmt)
        + _riff_chunk(b"data", b"\x00" * (frames * block_align))
        + _riff_chunk(b"acid", pack_acid_chunk(acid))
    )
    return b"RIFF" + struct.pack("<I", len(body)) + body
