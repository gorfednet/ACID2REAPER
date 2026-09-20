"""
Structural gate every generated ``.rpp`` must pass.

These are the invariants REAPER relies on and that a golden file would not
notice on its own: a golden only says "the same as last time", which is equally
true of consistently wrong output.
"""

from __future__ import annotations

import math
import re
from typing import Iterator, List

from rpp import loads
from rpp.element import Element

from acid2reaper.binary.meter import LEGAL_DENOMINATORS, MAX_NUMERATOR
from acid2reaper.model import PLAYRATE_MAX, PLAYRATE_MIN

_BAD_NUMBER = re.compile(r"\b(nan|-?inf(inity)?|[-+]?\d*\.?\d+e[-+]?\d+)\b", re.IGNORECASE)


def _walk(element: Element) -> Iterator[Element]:
    yield element
    for child in element.children:
        if isinstance(child, Element):
            yield from _walk(child)


def _lines(element: Element, tag: str) -> List[list]:
    return [c for c in element.children if isinstance(c, list) and c and c[0] == tag]


def _elements(element: Element, tag: str) -> List[Element]:
    return [c for c in element.children if isinstance(c, Element) and c.tag == tag]


def _number(token: str) -> float:
    return float(token)


def assert_valid_rpp(text: str) -> Element:
    """Check a generated project and return the parsed root."""
    root = loads(text)
    assert root.tag == "REAPER_PROJECT", f"unexpected root tag {root.tag!r}"
    assert len(root.attrib) == 3, f"expected 3 root attributes, got {root.attrib!r}"

    tempo_lines = _lines(root, "TEMPO")
    assert len(tempo_lines) == 1, f"expected exactly one TEMPO line, got {len(tempo_lines)}"
    _, tempo, num, den = tempo_lines[0]
    assert math.isfinite(_number(tempo)) and 20.0 <= _number(tempo) <= 400.0, f"tempo {tempo}"
    assert 1 <= int(num) <= MAX_NUMERATOR, f"time signature numerator {num}"
    assert int(den) in LEGAL_DENOMINATORS, f"time signature denominator {den}"

    tracks = _elements(root, "TRACK")
    assert tracks, "project has no tracks"
    master_names = _lines(tracks[0], "NAME")
    assert master_names and master_names[0][1] == "", "first TRACK must be the master bus"

    for track in tracks:
        for item in _elements(track, "ITEM"):
            _assert_valid_item(item)

    for notes in _elements(root, "NOTES"):
        for child in notes.children:
            assert isinstance(child, str), f"NOTES child must be a plain string, got {type(child)}"
            assert child.startswith("|"), f"NOTES line must start with a pipe: {child!r}"

    assert not _BAD_NUMBER.search(text), "output contains nan/inf/scientific notation"
    control = {ch for ch in text if ch < " " and ch != "\n"}
    assert not control, f"output contains control characters: {control!r}"
    return root


def _assert_valid_item(item: Element) -> None:
    for tag in ("POSITION", "LENGTH", "SOFFS"):
        found = _lines(item, tag)
        assert len(found) == 1, f"ITEM needs exactly one {tag}, got {len(found)}"

    position = _number(_lines(item, "POSITION")[0][1])
    length = _number(_lines(item, "LENGTH")[0][1])
    soffs = _number(_lines(item, "SOFFS")[0][1])
    assert position >= 0, f"negative POSITION {position}"
    assert length > 0, f"non-positive LENGTH {length}"
    assert soffs >= 0, f"negative SOFFS {soffs}"

    sources = [c for c in item.children if isinstance(c, Element) and c.tag == "SOURCE"]
    assert len(sources) == 1, f"ITEM needs exactly one SOURCE, got {len(sources)}"
    files = _lines(sources[0], "FILE")
    assert len(files) == 1, f"SOURCE needs exactly one FILE, got {len(files)}"

    for playrate in _lines(item, "PLAYRATE"):
        assert len(playrate) == 9, f"PLAYRATE needs 8 values, got {len(playrate) - 1}"
        rate = abs(_number(playrate[1]))
        assert PLAYRATE_MIN <= rate <= PLAYRATE_MAX, f"playrate {rate} out of range"
        assert playrate[2] in ("0", "1"), f"preserve-pitch flag {playrate[2]!r}"
