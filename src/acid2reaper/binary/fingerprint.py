"""
Lightweight file “fingerprinting” for ACID projects.

We never execute anything from the file—we only inspect magic bytes, optional
GUIDs, and RIFF size coherence so downstream code can pick a parser strategy.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
import struct
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class Fingerprint:
    """Detected container / era for an .acd file."""

    family_id: str
    magic: str
    riff_form: Optional[str]
    guid_at_24: Optional[str]
    ole: bool
    zip_pk: bool
    riff_size_coherent: bool
    acid_pro_major_guess: Optional[int]


def _signatures_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "acd_signatures.json"


def _load_signatures() -> Dict[str, Any]:
    with _signatures_path().open("r", encoding="utf-8") as fp:
        return json.load(fp)


def _guid_le(data: bytes, offset: int) -> Optional[str]:
    if offset < 0 or offset + 16 > len(data):
        return None
    try:
        return str(uuid.UUID(bytes_le=data[offset : offset + 16]))
    except ValueError:
        return None


def _riff_size_ok(data: bytes) -> tuple[bool, Optional[str]]:
    if len(data) < 12:
        return False, None
    tag = data[:4]
    if tag not in (b"RIFF", b"RIFX", b"riff", b"rifx"):
        return False, None
    size = struct.unpack_from("<I", data, 4)[0]
    form = data[8:12]
    try:
        form_s = form.decode("ascii", errors="replace")
    except Exception:
        form_s = None
    coherent = size >= 4 and 8 + size <= len(data) and size < 2**31
    return coherent, form_s


def detect_fingerprint(raw: bytes) -> Fingerprint:
    """
    Classify an .acd by header magic and (when possible) stable GUID fingerprints.

    Matching uses `acd_signatures.json` sample entries plus generic rules.
    """
    data = raw
    ole = len(data) >= 8 and data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    zip_pk = len(data) >= 4 and data[:4] == b"PK\x03\x04"

    magic = data[:4].decode("ascii", errors="replace") if len(data) >= 4 else ""
    guid_24 = _guid_le(data, 24)

    coherent, form = _riff_size_ok(data)

    family = "unknown"
    major_guess: Optional[int] = None

    try:
        sig = _load_signatures()
        for sample in sig.get("samples", []):
            if sample.get("header_magic") == "riff" and guid_24:
                if sample.get("guid_bytes_le_offset_24") == guid_24:
                    family = sample.get("parser_family", "riff_lower_guid_shell")
                    guess = sample.get("acid_pro_major_guess") or []
                    if guess:
                        major_guess = int(guess[0])
                    break
    except (OSError, json.JSONDecodeError, KeyError):
        pass

    if family == "unknown":
        if ole:
            family = "ole_compound"
        elif zip_pk:
            family = "zip_bundle"
        elif data[:4] == b"RIFF" and coherent and form == "ACID":
            family = "riff_acid_standard"
        elif data[:4] == b"riff":
            family = "riff_lower_guid_shell"
        elif data[:4] == b"RIFF":
            family = "riff_generic"

    return Fingerprint(
        family_id=family,
        magic=magic,
        riff_form=form,
        guid_at_24=guid_24,
        ole=ole,
        zip_pk=zip_pk,
        riff_size_coherent=coherent,
        acid_pro_major_guess=major_guess,
    )
