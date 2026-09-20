"""
A :class:`ProjectSpec` transcription of the real ``DrumRollUpDemo.acd``.

This is the builder's anchor. ``tests/test_fixture_builder_anchor.py`` asserts
that building this spec reproduces the real file's decoded timeline and its leaf
payload bytes, which is what makes the synthetic fixtures in the rest of the
suite evidence rather than a restatement of the parser's own assumptions.
"""

from __future__ import annotations

from acid2reaper.binary.acid_chunk import AcidChunk

from .wave64 import MEDIA_IN_TRACK_RECORD, EventSpec, ProjectSpec, TrackSpec

#: The cached copy of the source WAV's own ``acid`` chunk.
DRUM_ROLL_SOURCE_ACID = AcidChunk(
    flags=0,
    root_note=0x3C,
    reserved_u16=0x8000,
    reserved_f32=0.0,
    beats=4,
    meter_den=4,
    meter_num=4,
    tempo_bpm=139.5569610595703,
)

#: Every event after a track's first carries this undecoded word; see
#: ``fixturelib.wave64._EVENT_TAIL_WORD``.
_TAIL = 492

DRUM_ROLL_EVENTS = (
    EventSpec(0, 98304),
    EventSpec(98304, 49152, _TAIL),
    EventSpec(147456, 49152, _TAIL),
    EventSpec(196608, 24576, _TAIL),
    EventSpec(221184, 24576, _TAIL),
    EventSpec(245760, 24576, _TAIL),
    EventSpec(270336, 24576, _TAIL),
    EventSpec(294912, 12289, _TAIL),
    EventSpec(307201, 12289, _TAIL),
    EventSpec(319490, 12289, _TAIL),
    EventSpec(331779, 12289, _TAIL),
    EventSpec(344068, 12289, _TAIL),
    EventSpec(356357, 12289, _TAIL),
    EventSpec(368646, 12289, _TAIL),
    EventSpec(380935, 12289, _TAIL),
)

DRUM_ROLL_UP_DEMO = ProjectSpec(
    tempo_bpm=120.0,
    sample_rate_hz=44100,
    ppq=24576,
    meter_num=4,
    meter_den=4,
    media_layout=MEDIA_IN_TRACK_RECORD,
    # The ACID 3-era build zeroes the meter here and keeps it in the project
    # record instead.
    meter_in_timebase=False,
    project_path=(
        "C:\\Program Files\\Sonic Foundry Beta\\ACID 3.0\\Temp\\"
        "ACID Pro Temp 6\\DrumRollUpDemo_1\\DrumRollUpDemo.acd"
    ),
    app_dir="C:\\Program Files\\Sonic Foundry Beta\\ACID 3.0\\",
    tracks=(
        TrackSpec(
            media_filename="Break Pattern c.WAV",
            display_name="Break Pattern c",
            events=DRUM_ROLL_EVENTS,
            source_acid=DRUM_ROLL_SOURCE_ACID,
        ),
    ),
)
