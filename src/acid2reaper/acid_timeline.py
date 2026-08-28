"""Conservative handling of still-undecoded ACID clip properties."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from .binary.extract import StructuredFields
from .binary.fingerprint import Fingerprint
from .model import AcidProject


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


def extract_clip_timeline_props(
    raw: bytes,
    fp: Fingerprint,
    structured: StructuredFields,
    scan_blob: bytes,
) -> Dict[str, ClipTimelineProps]:
    """Return no properties until their binary fields have been verified.

    Earlier code treated arbitrary nearby values as gain and pitch. In the
    catalogued ACID 3 fixture, the apparent ``-100`` pitch value is a version
    field, so exporting it would fabricate an edit.
    """

    _ = raw, fp, structured, scan_blob
    return {}


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
