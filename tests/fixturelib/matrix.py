"""
The synthetic fixture matrix.

One real project exists, in 4/4 at 120 BPM with a single track. Everything the
converter claims to handle beyond that -- odd meters, one-shots, multiple
tracks, other build layouts -- is covered here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple

from acid2reaper.binary.acid_chunk import FLAG_ACIDIZER, FLAG_ONE_SHOT, AcidChunk

from .wav import build_acidized_wav
from .wave64 import (
    MEDIA_IN_DEDICATED_LEAF,
    MEDIA_IN_TRACK_RECORD,
    EventSpec,
    ProjectSpec,
    TrackSpec,
)

PPQ = 24576


def _bars(count: int, meter_num: int = 4, ticks_per_beat: int = PPQ) -> int:
    return count * meter_num * ticks_per_beat


def _events(count: int, length_ticks: int, start: int = 0) -> Tuple[EventSpec, ...]:
    return tuple(
        EventSpec(start + i * length_ticks, length_ticks, tail_word=0 if i == 0 else 492)
        for i in range(count)
    )


@dataclass(frozen=True)
class Case:
    id: str
    spec: ProjectSpec
    media: Dict[str, bytes] = field(default_factory=dict)
    note: str = ""


def _case(
    case_id: str,
    *,
    note: str,
    tempo: float,
    meter: Tuple[int, int] = (4, 4),
    source: AcidChunk | None = None,
    events: Tuple[EventSpec, ...] | None = None,
    filename: str = "loop.wav",
    write_media: bool = True,
    **spec_kwargs,
) -> Case:
    meter_num, meter_den = meter
    if source is None:
        source = AcidChunk(
            flags=FLAG_ACIDIZER,
            beats=meter_num,
            meter_num=meter_num,
            meter_den=meter_den,
            tempo_bpm=tempo,
        )
    if events is None:
        events = _events(4, meter_num * PPQ)
    spec_kwargs.setdefault("ppq", PPQ)
    spec = ProjectSpec(
        tempo_bpm=tempo,
        meter_num=meter_num,
        meter_den=meter_den,
        tracks=(TrackSpec(filename, events=events, source_acid=source),),
        **spec_kwargs,
    )
    media = {filename: build_acidized_wav(acid=source)} if write_media else {}
    return Case(case_id, spec, media, note)


def _build_cases() -> Tuple[Case, ...]:
    cases = [
        _case(
            "m4_4",
            note="Baseline: the meter the only real project uses.",
            tempo=120.0,
            meter=(4, 4),
            meter_in_timebase=True,
        ),
        _case(
            "m3_4",
            note="3 is not a power of two, so the pair resolves regardless of order.",
            tempo=90.0,
            meter=(3, 4),
            meter_in_timebase=True,
        ),
        _case(
            "m5_4",
            note="Self-resolving, and a non-44100 sample rate.",
            tempo=100.0,
            meter=(5, 4),
            sample_rate_hz=48000,
            meter_in_timebase=True,
        ),
        _case(
            "m7_8",
            note="Self-resolving compound meter.",
            tempo=140.0,
            meter=(7, 8),
            meter_in_timebase=True,
        ),
        _case(
            "m6_8",
            note="6 is not a power of two either, so 6/8 is unambiguous.",
            tempo=110.0,
            meter=(6, 8),
            meter_in_timebase=True,
        ),
        _case(
            "m12_8",
            note="Numerator above 8; pins the x/8 tick-scaling assumption.",
            tempo=70.0,
            meter=(12, 8),
            meter_in_timebase=True,
        ),
        _case(
            "meter_only_in_project_record",
            note="ACID 3-era layout: timebase meter zeroed, project record carries it.",
            tempo=120.0,
            meter=(3, 4),
            meter_in_timebase=False,
        ),
        _case(
            "one_shot",
            note="A one-shot must not be stretched, whatever its cached tempo says.",
            tempo=120.0,
            source=AcidChunk(
                flags=FLAG_ACIDIZER | FLAG_ONE_SHOT,
                beats=4,
                tempo_bpm=174.0,
            ),
            meter_in_timebase=True,
        ),
        _case(
            "stretched_loop",
            note="The companion to one_shot: a loop authored at another tempo.",
            tempo=120.0,
            source=AcidChunk(flags=FLAG_ACIDIZER, beats=4, tempo_bpm=174.0),
            meter_in_timebase=True,
        ),
        _case(
            "no_source_chunk",
            note="No cached acid chunk at all; playrate must stay at unity.",
            tempo=128.0,
            source=None,
            meter_in_timebase=True,
        ),
        _case(
            "odd_ppq_and_tempo",
            note="Non-default PPQ and a tempo that is not a round number.",
            tempo=133.0,
            sample_rate_hz=48000,
            ppq=4096,
            events=_events(4, 4 * 4096),
            meter_in_timebase=True,
        ),
        _case(
            "unaligned_filename",
            note="Odd-length name, so the builder emits padding and _align8 runs.",
            tempo=120.0,
            filename="odd name 7.wav",
            events=_events(1, 4 * PPQ),
            meter_in_timebase=True,
        ),
        _case(
            "missing_media",
            note="Project references a file that is not on disk.",
            tempo=120.0,
            write_media=False,
            meter_in_timebase=True,
        ),
    ]

    # Two tracks of different sources, one of them a one-shot, in the newer
    # build layout where the media reference lives in its own leaf.
    loop = AcidChunk(flags=FLAG_ACIDIZER, beats=4, tempo_bpm=96.0)
    hit = AcidChunk(flags=FLAG_ACIDIZER | FLAG_ONE_SHOT, beats=1, tempo_bpm=120.0)
    pad = AcidChunk(flags=FLAG_ACIDIZER, beats=8, tempo_bpm=128.0)
    cases.append(
        Case(
            "multitrack_media_leaf",
            ProjectSpec(
                tempo_bpm=128.0,
                meter_num=4,
                meter_den=4,
                ppq=PPQ,
                meter_in_timebase=True,
                media_layout=MEDIA_IN_DEDICATED_LEAF,
                tracks=(
                    TrackSpec("bass loop.wav", events=_events(4, 4 * PPQ), source_acid=loop),
                    TrackSpec("stab.wav", events=_events(2, PPQ, start=8 * PPQ), source_acid=hit),
                    TrackSpec("pad.wav", events=_events(1, 8 * PPQ), source_acid=pad),
                    # A track with no events at all: it must survive, or every
                    # track after it is silently renumbered.
                    TrackSpec("unused.wav", events=(), source_acid=loop),
                ),
            ),
            {
                "bass loop.wav": build_acidized_wav(acid=loop),
                "stab.wav": build_acidized_wav(acid=hit),
                "pad.wav": build_acidized_wav(acid=pad),
                "unused.wav": build_acidized_wav(acid=loop),
            },
            "Several sources per project, the newer media layout, and an empty track.",
        )
    )
    cases.append(
        Case(
            "multitrack_track_record",
            ProjectSpec(
                tempo_bpm=98.0,
                meter_num=4,
                meter_den=4,
                ppq=PPQ,
                meter_in_timebase=True,
                media_layout=MEDIA_IN_TRACK_RECORD,
                tracks=(
                    TrackSpec("drums.wav", events=_events(3, 4 * PPQ), source_acid=loop),
                    TrackSpec("keys.wav", events=_events(2, 8 * PPQ), source_acid=pad),
                ),
            ),
            {
                "drums.wav": build_acidized_wav(acid=loop),
                "keys.wav": build_acidized_wav(acid=pad),
            },
            "The older layout, where the media path sits in the track record.",
        )
    )
    return tuple(cases)


CASES: Tuple[Case, ...] = _build_cases()
