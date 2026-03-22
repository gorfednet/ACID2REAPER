"""
Best-effort discovery of mixer-related strings in ACID project bytes (FX names,
busses, groups). REAPER needs concrete ``FXID`` values to load plug-ins; we only
record hints here for release notes / future mapping.
"""

from __future__ import annotations

import re
from typing import List

from .string_scan import utf16le_ascii_runs


def _looks_like_mixer_hint(text: str) -> bool:
    low = text.lower()
    return any(
        k in low
        for k in (
            ".dll",
            "vst",
            "vst3",
            "dx:",
            "directx",
            "group",
            "bus",
            "send",
            "return",
            "master",
        )
    )


def collect_plugin_and_bus_hints(scan_blob: bytes) -> List[str]:
    """
    Return unique short strings that look like plug-in or bus identifiers.

    These are **not** wired into :class:`~acid2reaper.model.FxSlot` without a
    valid REAPER ``FXID``; they are appended to :attr:`AcidProject.notes`.
    """
    hints: List[str] = []
    for _off, raw in utf16le_ascii_runs(scan_blob):
        s = raw.strip()
        if len(s) >= 200:
            continue
        if _looks_like_mixer_hint(s) and s not in hints:
            hints.append(s)

    # ASCII runs (plugin paths often stored as ANSI).
    for m in re.finditer(rb"[A-Za-z]:\\[^\x00\r\n]{4,200}\.dll", scan_blob, re.I):
        s = m.group(0).decode("ascii", errors="ignore")
        if s not in hints:
            hints.append(s)
    return hints[:64]
