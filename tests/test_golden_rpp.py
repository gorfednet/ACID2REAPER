"""
Golden-file coverage of the whole fixture matrix.

Goldens only ever say "the same as last time", which is equally true of
consistently wrong output, so every case is also put through
``assert_valid_rpp`` and through explicit behavioural assertions below.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from acid2reaper.cli import convert
from fixturelib.matrix import CASES
from fixturelib.rpp_assert import assert_valid_rpp
from fixturelib.wave64 import build_acd

GOLDEN_DIR = Path(__file__).resolve().parent / "fixtures" / "golden"
UPDATE_ENV = "ACID2REAPER_UPDATE_GOLDEN"


def normalize_rpp_text(text: str, root: Path) -> str:
    """
    Make output comparable across machines and platforms.

    Without this the goldens embed an absolute tmp_path and the native path
    separator, so they would be rewritten by every run and could never pass on
    more than one operating system.
    """
    for candidate in {str(root), str(root.resolve())}:
        text = text.replace(candidate.replace("\\", "\\\\"), "<TMP>")
        text = text.replace(candidate, "<TMP>")
    text = re.sub(r"<TMP>[\\/]", "<TMP>/", text)
    return text.replace("\\", "/")


def render_case(case, work: Path) -> str:
    acd = work / f"{case.id}.acd"
    acd.write_bytes(build_acd(case.spec))
    for name, blob in case.media.items():
        (work / name).write_bytes(blob)

    out = work / f"{case.id}.rpp"
    convert(acd, out)
    text = out.read_text(encoding="utf-8")
    assert_valid_rpp(text)
    return normalize_rpp_text(text, work)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_golden_rpp(case, tmp_path: Path) -> None:
    actual = render_case(case, tmp_path)
    golden = GOLDEN_DIR / f"{case.id}.rpp"

    if os.environ.get(UPDATE_ENV) == "1":
        golden.parent.mkdir(parents=True, exist_ok=True)
        with golden.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(actual)
        pytest.skip(f"golden regenerated: {golden.name}")

    assert golden.exists(), f"missing golden for {case.id}; run scripts/update_goldens.py"
    assert actual == golden.read_text(encoding="utf-8"), (
        f"{case.id} output changed; review the diff, then regenerate with "
        f"scripts/update_goldens.py if the change is intended"
    )


@pytest.mark.parametrize(
    "case_id, expected",
    [
        ("m4_4", "4 4"),
        ("m3_4", "3 4"),
        ("m5_4", "5 4"),
        ("m7_8", "7 8"),
        ("m6_8", "6 8"),
        ("m12_8", "12 8"),
        ("meter_only_in_project_record", "3 4"),
    ],
)
def test_time_signature_survives_the_round_trip(case_id: str, expected: str, tmp_path: Path) -> None:
    """The meter used to be unreachable, so every project came out as 4/4."""
    case = next(c for c in CASES if c.id == case_id)
    text = render_case(case, tmp_path)
    tempo_line = next(line for line in text.splitlines() if line.strip().startswith("TEMPO"))
    assert tempo_line.split(maxsplit=1)[1].split(" ", 1)[1] == expected


def _item_playrates(text: str) -> list[str]:
    """Item PLAYRATE lines only, never the project-level master playrate."""
    return [
        line.split()[1]
        for line in text.splitlines()
        if line.strip().startswith("PLAYRATE") and len(line.split()) == 9
    ]


def test_one_shot_case_has_no_playrate(tmp_path: Path) -> None:
    case = next(c for c in CASES if c.id == "one_shot")
    text = render_case(case, tmp_path)
    assert _item_playrates(text) == []
    assert "One-shot sources left unstretched" in text
    # The cached 174 BPM was not applied, so it must not be reported as stretch.
    assert "derived from cached source loop tempo" not in text


def test_stretched_loop_case_does_have_a_playrate(tmp_path: Path) -> None:
    """Same project but without the one-shot bit: the loop is beat-mapped."""
    case = next(c for c in CASES if c.id == "stretched_loop")
    text = render_case(case, tmp_path)
    rates = _item_playrates(text)
    assert rates, "expected a beat-mapped clip"
    assert all(abs(float(r) - 120.0 / 174.0) < 1e-9 for r in rates)


def test_empty_track_is_preserved(tmp_path: Path) -> None:
    """Dropping event-less tracks renumbered everything after them."""
    case = next(c for c in CASES if c.id == "multitrack_media_leaf")
    text = render_case(case, tmp_path)
    assert text.count("<TRACK") == 1 + len(case.spec.tracks)
    # The track survives with its name even though it contributes no items.
    assert "NAME unused" in text


def test_each_track_keeps_its_own_media(tmp_path: Path) -> None:
    """Newer builds hid the media path, collapsing every track onto one file."""
    case = next(c for c in CASES if c.id == "multitrack_media_leaf")
    text = render_case(case, tmp_path)
    # Only tracks that place events contribute a FILE line; the empty track
    # legitimately does not.
    for track in case.spec.tracks:
        if track.events:
            assert track.media_filename in text, f"{track.media_filename} missing"
    files = [ln for ln in text.splitlines() if ln.strip().startswith("FILE")]
    assert len({ln.strip() for ln in files}) == 3, "each track must keep its own source"


def test_no_cached_chunk_means_unity_playrate(tmp_path: Path) -> None:
    case = next(c for c in CASES if c.id == "no_source_chunk")
    text = render_case(case, tmp_path)
    assert _item_playrates(text) == []


def test_missing_media_is_reported(tmp_path: Path) -> None:
    case = next(c for c in CASES if c.id == "missing_media")
    text = render_case(case, tmp_path)
    assert "media not found on disk" in text
