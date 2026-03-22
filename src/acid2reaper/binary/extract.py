"""
Structured field extraction layered on top of :func:`detect_fingerprint`.

Think of this module as “what we can read with confidence once we know which
family the file belongs to.” Exact GUID matches use offsets recorded in
``acd_signatures.json``; generic families fall back to field tables in the
same JSON. OLE and RIFF helpers are optional extras.
"""

from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .fingerprint import Fingerprint, detect_fingerprint
from .ole_extract import ole_concat_stream_bytes
from .riff import collect_strings_from_riff, parse_riff_tree


@dataclass
class StructuredFields:
    """Fields read from a version-specific layout (best-effort)."""

    tempo_bpm: Optional[float] = None
    sample_rate_hz: Optional[int] = None
    riff_strings: Optional[List[str]] = None
    signature_id: Optional[str] = None
    ole_stream_bytes: Optional[bytes] = None


def _load_json() -> Dict[str, Any]:
    path = Path(__file__).resolve().parent.parent / "data" / "acd_signatures.json"
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def _read_float64_le(data: bytes, offset: int) -> Optional[float]:
    if offset < 0 or offset + 8 > len(data):
        return None
    v = struct.unpack_from("<d", data, offset)[0]
    if not math.isfinite(v):
        return None
    return float(v)


def _read_u32_le(data: bytes, offset: int) -> Optional[int]:
    if offset < 0 or offset + 4 > len(data):
        return None
    return int(struct.unpack_from("<I", data, offset)[0])


def _apply_family_fields(
    family_id: str, data: bytes, sig: Dict[str, Any]
) -> StructuredFields:
    out = StructuredFields()
    for fam in sig.get("families", []):
        if fam.get("id") != family_id:
            continue
        fields = fam.get("fields") or {}
        for key, spec in fields.items():
            enc = spec.get("encoding")
            off = int(spec.get("offset", -1))
            if enc == "float64_le":
                v = _read_float64_le(data, off)
                if v is not None and 20 < v < 400:
                    out.tempo_bpm = v
            elif enc == "uint32_le":
                v = _read_u32_le(data, off)
                if v in (
                    8000,
                    11025,
                    12000,
                    16000,
                    22050,
                    24000,
                    32000,
                    44100,
                    48000,
                    88200,
                    96000,
                    192000,
                ):
                    out.sample_rate_hz = v
        break
    return out


def _match_sample_record(data: bytes, sig: Dict[str, Any]) -> Optional[StructuredFields]:
    """If raw bytes match a catalogued sample fingerprint, use verified offsets."""
    try:
        import uuid

        guid_24 = None
        if len(data) >= 40:
            guid_24 = str(uuid.UUID(bytes_le=data[24:40]))
    except Exception:
        guid_24 = None

    for sample in sig.get("samples", []):
        if sample.get("guid_bytes_le_offset_24") and guid_24 == sample.get(
            "guid_bytes_le_offset_24"
        ):
            vc = sample.get("verified_constants") or {}
            out = StructuredFields(signature_id=sample.get("id"))
            off_t = vc.get("tempo_bpm_double_le_offset")
            if isinstance(off_t, int):
                t = _read_float64_le(data, off_t)
                if t is not None:
                    out.tempo_bpm = t
            for key in ("sample_rate_hz_u32_le_offsets", "sample_rate_hz_u32_le_offset"):
                offs = vc.get(key)
                if isinstance(offs, int):
                    offs = [offs]
                if isinstance(offs, list):
                    for o in offs:
                        if isinstance(o, int):
                            sr = _read_u32_le(data, o)
                            if sr in (
                                8000,
                                11025,
                                16000,
                                22050,
                                32000,
                                44100,
                                48000,
                                96000,
                            ):
                                out.sample_rate_hz = sr
                                break
                    if out.sample_rate_hz:
                        break
            return out
    return None


def extract_structured_fields(raw: bytes) -> tuple[Fingerprint, StructuredFields]:
    """
    Detect format fingerprint and extract structured fields when a signature matches.

    Falls back to partial RIFF walking (valid RIFF only) or OLE stream concatenation.
    """
    fp = detect_fingerprint(raw)
    sig = _load_json()
    structured = _match_sample_record(raw, sig) or StructuredFields()

    if structured.signature_id is None:
        fam = fp.family_id
        if fam in ("riff_lower_guid_shell",):
            merged = _apply_family_fields("riff_lower_guid_shell", raw, sig)
            if merged.tempo_bpm:
                structured.tempo_bpm = merged.tempo_bpm
            if merged.sample_rate_hz:
                structured.sample_rate_hz = merged.sample_rate_hz

    if fp.family_id in ("riff_acid_standard", "riff_generic") and fp.riff_size_coherent:
        tree = parse_riff_tree(raw, 0)
        if tree is not None and getattr(tree, "form_fourcc", None) == "ACID":
            structured.riff_strings = collect_strings_from_riff(raw)

    if fp.ole or raw[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        blob = ole_concat_stream_bytes(raw)
        if blob:
            structured.ole_stream_bytes = blob

    return fp, structured
