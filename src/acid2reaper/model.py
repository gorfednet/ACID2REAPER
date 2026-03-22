from __future__ import annotations

"""
In-memory representation of a project after parsing.

These dataclasses are intentionally boring: plain fields, no behavior, so both
the CLI and GUI can share them without dragging in I/O or UI dependencies.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class AcidClip:
    """One media region in an ACID timeline (best-effort extraction)."""

    path: Path
    position_sec: float = 0.0
    length_sec: Optional[float] = None
    name: str = ""


@dataclass
class AcidTrack:
    name: str
    clips: List[AcidClip] = field(default_factory=list)


@dataclass
class AcidProject:
    """Normalized project data used to build an RPP."""

    source_path: Path
    tempo_bpm: float = 120.0
    time_sig_num: int = 4
    time_sig_den: int = 4
    sample_rate: Optional[int] = None
    tracks: List[AcidTrack] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    format_family: str = "unknown"
    format_signature_id: Optional[str] = None
    acid_pro_major_guess: Optional[int] = None
