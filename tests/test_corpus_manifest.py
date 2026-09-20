"""
Offline assertions over the real-project corpus manifest.

The manifest summarises 245 real ACID projects spanning roughly 2005-2008 and
thirty distinct build layouts. The files themselves are private music and are
not in this repository; what is committed is their structural fingerprint.

These tests run everywhere and need nothing but the JSON. They are what stops a
future change quietly regressing a build generation nobody has a sample of.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from acid2reaper.binary.acid_chunk import FLAG_ONE_SHOT, KNOWN_FLAGS
from acid2reaper.binary.meter import LEGAL_DENOMINATORS, MAX_NUMERATOR
from acid2reaper.binary.wave64 import tempo_from_usec_per_beat

MANIFEST_PATH = Path(__file__).resolve().parent / "fixtures" / "corpus_manifest.json"
MANIFEST = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
PROJECTS = MANIFEST["projects"]
DECODED = [p for p in PROJECTS if p.get("timeline")]


def test_manifest_shape() -> None:
    assert MANIFEST["schema"] == 1
    assert MANIFEST["project_count"] == len(PROJECTS)
    # Large enough to be a real corpus; the exact count depends on whoever
    # regenerated it, so assert the floor rather than a brittle equality.
    assert len(PROJECTS) >= 200
    assert len(MANIFEST["layouts"]) >= 20


def test_the_manifest_carries_nothing_identifying() -> None:
    """
    The corpus is private music in a public repository.

    Media references are salted hashes plus a bare extension; if a future change
    to the builder started emitting real paths, this fails.
    """
    text = MANIFEST_PATH.read_text(encoding="utf-8")
    for marker in ("C:\\\\", "D:\\\\", "/Users/", "\\\\Documents", ".acd"):
        assert marker not in text, f"manifest leaks {marker!r}"


def test_every_project_decodes() -> None:
    """Regression guard: two of these used to fail outright before the parser fixes."""
    unparsed = [p["id"] for p in PROJECTS if not p["parsed"]]
    assert unparsed == []
    undecoded = [p["id"] for p in PROJECTS if not p.get("timeline")]
    assert undecoded == []


def test_no_project_loses_all_of_its_media() -> None:
    """
    Newer builds moved the media reference to its own leaf.

    Before that layout was handled, 31 projects resolved zero paths and every
    one of their tracks collapsed onto a single fallback file.
    """
    starved = [p["id"] for p in DECODED if p["timeline"]["tracks_with_media"] == 0]
    assert starved == []


def test_media_resolution_is_near_total() -> None:
    total = sum(p["timeline"]["track_count"] for p in DECODED)
    resolved = sum(p["timeline"]["tracks_with_media"] for p in DECODED)
    assert total > 5000
    assert resolved / total > 0.99


def test_tempo_is_not_uniformly_the_default() -> None:
    """
    The old decoder read a template field that is 120.0 in every real project.

    A corpus of 245 projects collapsing to one tempo is exactly the symptom;
    assert the spread instead of the absence.
    """
    tempos = {p["timeline"]["tempo_bpm"] for p in DECODED}
    assert len(tempos) >= 25
    assert min(tempos) >= 20.0 and max(tempos) <= 400.0


@pytest.mark.parametrize("project", DECODED, ids=lambda p: p["id"])
def test_recorded_timing_is_self_consistent(project) -> None:
    timeline = project["timeline"]
    timebase = project["timebase"]
    if timebase is not None:
        assert timebase["ppq"] == timeline["ppq"] > 0
        assert timebase["usec_per_beat"] > 0
        # The tempo in the timeline must be the one the timebase encodes.
        assert timeline["tempo_bpm"] == tempo_from_usec_per_beat(timebase["usec_per_beat"])
    else:
        # One damaged file in the corpus has no timebase chunk. Falling back to
        # the project record's default is all we can honestly do there.
        assert timeline["tempo_bpm"] > 0

    num, den = timeline["time_sig"]
    assert 1 <= num <= MAX_NUMERATOR
    assert den in LEGAL_DENOMINATORS

    assert timeline["track_count"] >= 1
    assert 0 <= timeline["tracks_with_media"] <= timeline["track_count"]
    assert len(timeline["tracks_digest"]) == 64


def test_corpus_contains_real_one_shots() -> None:
    """
    The one-shot fix is not hypothetical.

    97 of these projects carry a source with the one-shot bit set, and every one
    of them used to be resampled to the project tempo, which retunes a hit.
    """
    with_one_shots = [
        p for p in DECODED if any(f & FLAG_ONE_SHOT for f in p["timeline"]["source_loop_flags"])
    ]
    assert len(with_one_shots) >= 90


def test_observed_flag_values_are_all_known_bits() -> None:
    """If a real file ever sets a bit we have no name for, we should hear about it."""
    observed = {f for p in DECODED for f in p["timeline"]["source_loop_flags"]}
    assert observed
    unknown = {f for f in observed if f & ~KNOWN_FLAGS}
    assert unknown == set(), f"unrecognised acid flag bits: {unknown}"


def test_essentially_every_project_carries_a_timebase_record() -> None:
    """
    The timebase record is where the real tempo lives, so its presence matters.

    Exactly one file in the corpus lacks it: a damaged project whose root size
    was never backfilled. Anything more than that is a decoding regression.
    """
    without = [p["id"] for p in DECODED if p["timebase"] is None]
    assert len(without) <= 1


def test_corpus_spans_several_build_generations() -> None:
    """A single-layout corpus would not prove cross-build support."""
    used = {p["layout"] for p in DECODED}
    assert len(used) >= 20
