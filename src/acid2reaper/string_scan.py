"""
Shared helpers for scanning raw project bytes for embedded text.

ACID projects often store Windows-style paths as UTF-16LE runs of printable ASCII.
Several modules need the same walk; keeping it here avoids drift and keeps call
sites small.
"""

from __future__ import annotations

from typing import Callable, List, Tuple


def utf16le_ascii_runs(
    data: bytes,
    *,
    min_run_bytes: int = 8,
    min_chars: int = 4,
) -> List[Tuple[int, str]]:
    """
    Yield ``(byte_offset, text)`` for contiguous UTF-16LE ASCII runs.

    Only characters in the printable ASCII range are collected; this matches how
    Sonic Foundry-era projects embedded paths and labels next to binary records.
    """
    out: List[Tuple[int, str]] = []
    i = 0
    n = len(data)
    while i < n - 1:
        b0, b1 = data[i], data[i + 1]
        if b1 != 0 or b0 < 32 or b0 > 126:
            i += 1
            continue
        start = i
        chars: List[str] = []
        j = i
        while j < n - 1 and data[j + 1] == 0 and 32 <= data[j] <= 126:
            chars.append(chr(data[j]))
            j += 2
        if j - start >= min_run_bytes and len(chars) >= min_chars:
            out.append((start, "".join(chars)))
        i = j if j > i else i + 1
    return out


def utf16le_runs_filtered(
    data: bytes,
    keep: Callable[[str], bool],
) -> List[Tuple[int, str]]:
    """
    Like :func:`utf16le_ascii_runs`, but only entries whose **stripped** text passes ``keep``.

    Returned strings are stripped so callers (e.g. path length after the blob offset) stay consistent.
    """
    out: List[Tuple[int, str]] = []
    for offset, raw in utf16le_ascii_runs(data):
        text = raw.strip()
        if keep(text):
            out.append((offset, text))
    return out
