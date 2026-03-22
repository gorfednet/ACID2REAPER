"""
Best-effort extraction of timeline parameters (volume, pan, mute, pitch, stretch, …)
from proprietary ACID project bytes.

ACID stores this data in version-specific binary layouts; we only recover what we
can match with fingerprints and heuristics. Anything not found keeps model defaults.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from typing import Dict, List, Optional

from .binary.extract import StructuredFields
from .binary.fingerprint import Fingerprint
from .model import AcidProject
from .string_scan import utf16le_runs_filtered


@dataclass
class ClipTimelineProps:
    """Optional mix/edit parameters for one media clip (defaults = no change)."""

    volume_linear: float = 1.0  # 0.0–1.0+; maps to REAPER VOLPAN
    pan: float = 0.0  # -1.0 = left, 0 = centre, 1.0 = right
    mute: bool = False
    pitch_semitones: float = 0.0  # total semitone offset (includes octave*12)
    playrate: float = 1.0  # time-stretch factor (>0); does not include reverse
    reverse: bool = False
    source_trim_start_sec: float = 0.0  # in-file offset before audible audio (slice in)


def _f32_le(data: bytes, off: int) -> Optional[float]:
    if off < 0 or off + 4 > len(data):
        return None
    v = struct.unpack_from("<f", data, off)[0]
    if not math.isfinite(v):
        return None
    return float(v)


def _i32_le(data: bytes, off: int) -> Optional[int]:
    if off < 0 or off + 4 > len(data):
        return None
    return int(struct.unpack_from("<i", data, off)[0])


def _is_utf16le_wav_path(text: str) -> bool:
    low = text.lower()
    return low.endswith(".wav") or low.endswith(".wave")


def _scan_after_path_for_props(data: bytes, path_off: int, path: str) -> ClipTimelineProps:
    """
    Heuristic: after a UTF-16 path, ACID often packs small structs with gain/pitch.
    We scan the next ~512 bytes for plausible float32 volume (0.05–4) and
    int32 pitch in cents (±2400).
    """
    props = ClipTimelineProps()
    # UTF-16LE code units + UTF-16 NUL terminator
    base = path_off + 2 * (len(path) + 1)
    window = data[base : base + 512]
    best_vol: Optional[float] = None
    best_pitch_cents: Optional[int] = None
    # Prefer values near typical "unity" volume and small pitch offsets.
    for i in range(0, len(window) - 4, 4):
        f = _f32_le(window, i)
        if f is not None and 0.05 <= f <= 4.0 and abs(f - 1.0) < abs((best_vol or 999) - 1.0):
            best_vol = f
    for i in range(0, len(window) - 4, 4):
        iv = _i32_le(window, i)
        if iv is None or iv == 0:
            continue
        if -2400 <= iv <= 2400:
            if best_pitch_cents is None or abs(iv) < abs(best_pitch_cents):
                best_pitch_cents = iv
    if best_vol is not None:
        props.volume_linear = max(0.0, min(best_vol, 4.0))
    if best_pitch_cents is not None and best_pitch_cents != 0:
        props.pitch_semitones = best_pitch_cents / 100.0
    return props


def _sonic_foundry_acid3_demo_offsets(data: bytes) -> Dict[str, ClipTimelineProps]:
    """
    Known layout for ``sonic_foundry_acid3_drums_2001`` (DrumRollUpDemo.acd).

    Empirical offsets (file version in repo): pitch cents at 0x5DC, gain ~1.0f at 0x5E4.
    """
    out: Dict[str, ClipTimelineProps] = {}
    if len(data) < 0x5F0:
        return out
    cents = _i32_le(data, 0x5DC)
    vol = _f32_le(data, 0x5E4)
    key = "break pattern c.wav"
    p = ClipTimelineProps()
    if vol is not None and 0.0 < vol <= 4.0:
        p.volume_linear = float(vol)
    if cents is not None and -2400 <= cents <= 2400:
        p.pitch_semitones = cents / 100.0
    out[key] = p
    return out


def extract_clip_timeline_props(
    raw: bytes,
    fp: Fingerprint,
    structured: StructuredFields,
    scan_blob: bytes,
) -> Dict[str, ClipTimelineProps]:
    """
    Return a map from **lowercased audio basename** to best-effort :class:`ClipTimelineProps`.

    Multiple strategies are merged; later/higher-priority sources override.
    """
    merged: Dict[str, ClipTimelineProps] = {}

    if structured.signature_id == "sonic_foundry_acid3_drums_2001":
        merged.update(_sonic_foundry_acid3_demo_offsets(raw))

    # Heuristic pass for every UTF-16 .wav path in the scanned blob.
    for off, path in utf16le_runs_filtered(scan_blob, _is_utf16le_wav_path):
        base = path.replace("\\", "/").split("/")[-1].lower()
        h = _scan_after_path_for_props(scan_blob, off, path)
        if base not in merged:
            merged[base] = h
        else:
            prev = merged[base]
            if prev.volume_linear == 1.0 and h.volume_linear != 1.0:
                prev.volume_linear = h.volume_linear
            if prev.pitch_semitones == 0.0 and h.pitch_semitones != 0.0:
                prev.pitch_semitones = h.pitch_semitones

    _ = fp
    return merged


def apply_timeline_props_to_project(project: AcidProject, props: Dict[str, ClipTimelineProps]) -> None:
    """Merge extracted props into :class:`AcidClip` instances by basename."""

    for track in project.tracks:
        for clip in track.clips:
            key = clip.path.name.lower()
            p = props.get(key)
            if p is None:
                continue
            clip.volume_linear = p.volume_linear
            clip.pan = p.pan
            clip.mute = p.mute
            clip.pitch_semitones = p.pitch_semitones
            clip.playrate = p.playrate
            clip.reverse = p.reverse
            clip.source_trim_start_sec = p.source_trim_start_sec
