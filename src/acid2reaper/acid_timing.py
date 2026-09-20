"""
Convert ACID tick positions to seconds.

ACID stores PPQ as pulses per quarter note and tempo as beats per minute.
Whether that BPM counts quarter notes or the meter's own beat unit is
**unverified**: every real project available is in 4/4, where the two are
identical. We assume quarter notes, which is correct for every x/4 meter and is
the no-change option for everything else.

The assumption is isolated here, and pinned by the x/8 golden files, so that a
real 6/8 or 7/8 project would show up as a visible diff pointing straight at
this function rather than as silently doubled clip positions.
"""

from __future__ import annotations

ASSUME_TEMPO_IS_QUARTER_NOTES = True


def seconds_per_tick(tempo_bpm: float, ppq: int, meter_den: int = 4) -> float:
    """Seconds represented by one PPQ tick at the given tempo."""
    if tempo_bpm <= 0 or ppq <= 0:
        raise ValueError("tempo_bpm and ppq must be positive")
    base = 60.0 / (tempo_bpm * ppq)
    if ASSUME_TEMPO_IS_QUARTER_NOTES:
        return base
    return base * (4.0 / meter_den)
