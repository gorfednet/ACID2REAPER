"""
Standard RIFF tree parsing (uppercase ``RIFF`` / ``LIST``) for coherent files.

Some ACID builds may emit valid RIFF with an ``ACID`` form type; many older
demos do **not** validate as RIFF at all—those are handled elsewhere.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class RiffChunk:
    id: str
    offset: int
    size: int
    data_offset: int
    children: List["RiffChunk"] = field(default_factory=list)
    form_fourcc: Optional[str] = None


def _fourcc(b: bytes) -> str:
    return b.decode("ascii", errors="replace")


def _parse_riff_payload(data: bytes, start: int, end: int) -> List[RiffChunk]:
    """Parse chunks in a RIFF payload (after form type)."""
    out: List[RiffChunk] = []
    pos = start
    while pos + 8 <= end:
        cid = data[pos : pos + 4]
        sz = struct.unpack_from("<I", data, pos + 4)[0]
        if sz > end - pos - 8 or sz < 0:
            break
        payload = pos + 8
        pad = sz + (sz & 1)
        ch = RiffChunk(
            id=_fourcc(cid),
            offset=pos,
            size=sz,
            data_offset=payload,
        )
        if cid in (b"LIST", b"list"):
            if payload + 4 <= end:
                ch.children = _parse_riff_payload(data, payload + 4, payload + sz)
        out.append(ch)
        pos += 8 + pad
    return out


def parse_riff_tree(data: bytes, offset: int = 0) -> Optional[RiffChunk]:
    """
    Parse a top-level RIFF/RIFX chunk when size is coherent with the buffer.
    Returns a synthetic root chunk or None if not valid RIFF.
    """
    if offset + 12 > len(data):
        return None
    tag = data[offset : offset + 4]
    if tag not in (b"RIFF", b"RIFX", b"riff", b"rifx"):
        return None
    sz = struct.unpack_from("<I", data, offset + 4)[0]
    if offset + 8 + sz > len(data) or sz < 4:
        return None
    form = data[offset + 8 : offset + 12]
    root = RiffChunk(
        id=_fourcc(tag),
        offset=offset,
        size=sz,
        data_offset=offset + 12,
        form_fourcc=_fourcc(form),
    )
    root.children = _parse_riff_payload(data, offset + 12, offset + 8 + sz)
    return root


def collect_strings_from_riff(data: bytes) -> List[str]:
    """Walk a valid RIFF tree and collect ASCII strings from chunk payloads."""
    root = parse_riff_tree(data, 0)
    if root is None:
        return []
    collected: List[str] = []

    def walk(ch: RiffChunk) -> None:
        if not ch.children:
            pl = data[ch.data_offset : ch.data_offset + ch.size]
            if pl.endswith(b"\x00"):
                pl = pl[:-1]
            if 1 < len(pl) < 4096 and all(32 <= b < 127 or b in (9,) for b in pl):
                try:
                    s = pl.decode("ascii", errors="strict").strip()
                    if s:
                        collected.append(s)
                except UnicodeDecodeError:
                    pass
        for c in ch.children:
            walk(c)

    for c in root.children:
        walk(c)
    return collected
