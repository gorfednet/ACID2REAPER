from __future__ import annotations

"""
In-memory representation of a project after parsing.

These dataclasses are intentionally boring: plain fields, no behavior, so both
the CLI and GUI can share them without dragging in I/O or UI dependencies.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass
class AcidClip:
    """One media region in an ACID timeline (best-effort extraction)."""

    path: Path
    position_sec: float = 0.0
    length_sec: Optional[float] = None
    name: str = ""
    # Mix / processing (optional; exported to RPP when non-default)
    volume_linear: float = 1.0
    pan: float = 0.0
    mute: bool = False
    pitch_semitones: float = 0.0
    playrate: float = 1.0
    reverse: bool = False
    # In-point into the media file (seconds). Exported as ITEM SNAPOFFS (approximate).
    source_trim_start_sec: float = 0.0


@dataclass
class FxSlot:
    """
    One effect slot on a track or the master bus.

    ``fxid_reaper`` is the REAPER ``FXID`` payload (hex inside ``{...}``) when known.
    Without it, the slot is listed in project notes only—REAPER needs a valid FXID
    to instantiate a plug-in.
    """

    name: str = ""
    fxid_reaper: Optional[str] = None
    wet: float = 1.0
    bypass: bool = False


@dataclass
class TrackSend:
    """Send from this track to another track index (REAPER AUXRECV target)."""

    dest_track_index: int
    volume_linear: float = 1.0
    pan: float = 0.0
    mute: bool = False


@dataclass
class MasterBus:
    """Master / main output bus (always exported as the first TRACK in RPP)."""

    volume_linear: float = 1.0
    pan: float = 0.0
    mute: bool = False
    solo_clear: bool = False
    fx: List[FxSlot] = field(default_factory=list)


@dataclass
class AcidTrack:
    """One mixer strip plus timeline clips."""

    name: str
    clips: List[AcidClip] = field(default_factory=list)
    # Track strip (mixer)
    volume_linear: float = 1.0
    pan: float = 0.0
    mute: bool = False
    solo: bool = False
    # REAPER: TRACKGROUP id (0 = none). Same id = same group for grouping.
    track_group_id: int = 0
    # REAPER CHANMODE (0 = default stereo routing for standard tracks).
    chan_mode: int = 0
    # REAPER TRACKTYPE (0 = normal audio track in simple layouts).
    track_type: int = 0
    # REAPER FOLDERDEPTH (0 = not a folder child; >0 = nested under folders).
    folder_depth: int = 0
    # Multi-channel source count hint (2 = stereo). Used with CHANMODE when != 2.
    channel_count: int = 2
    fx: List[FxSlot] = field(default_factory=list)
    sends: List[TrackSend] = field(default_factory=list)


@dataclass
class AcidProject:
    """Normalized project data used to build an RPP."""

    source_path: Path
    tempo_bpm: float = 120.0
    time_sig_num: int = 4
    time_sig_den: int = 4
    sample_rate: Optional[int] = None
    master: MasterBus = field(default_factory=MasterBus)
    tracks: List[AcidTrack] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    format_family: str = "unknown"
    format_signature_id: Optional[str] = None
    acid_pro_major_guess: Optional[int] = None
    # Plug-in / bus names seen in bytes but not mapped to FXID (informational).
    unmapped_plugin_hints: List[str] = field(default_factory=list)
