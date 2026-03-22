"""
Turn raw ACID project bytes into our neutral :class:`AcidProject` model (**ACID2Reaper**).

The pipeline is deliberately split into small steps so newcomers can follow it:

1. **Fingerprint** the binary (:mod:`acid2reaper.binary.extract`) to pull tempo /
   sample rate when we recognize the layout.
2. **Scan** for path-like strings (UTF-16 Windows paths are common; ASCII paths
   appear in some builds).
3. **Resolve** each string to a real filesystem path next to the project or
   under optional media folders.
4. **Build tracks**—one track per unique audio basename, which matches many
   simple ACID loop projects (not every complex session).

Anything that looks like timeline editing (automation, stretch, pitch maps) is
out of scope until we have per-version binary specs.
"""

from __future__ import annotations

import math
import re
import struct
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

from .binary.extract import extract_structured_fields
from .containers import AUDIO_EXT
from .model import AcidClip, AcidProject, AcidTrack


def _utf16le_strings(data: bytes) -> List[Tuple[int, str]]:
    """Extract plausible UTF-16LE ASCII runs (Windows paths and filenames)."""
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
        if j - start >= 8 and len(chars) >= 4:
            out.append((start, "".join(chars)))
        i = j if j > i else i + 1
    return out


def _ascii_audio_paths(data: bytes) -> List[Tuple[int, str]]:
    """Find ASCII-like full paths or filenames ending in known audio extensions."""
    ext_group = "|".join(re.escape(e[1:]) for e in sorted(AUDIO_EXT, key=len, reverse=True))
    pat = re.compile(
        rb"(?:[A-Za-z]:\\[^\x00\r\n]{0,220}|(?:/[^\x00\r\n]+)+|[^\x00\r\n/]{1,200})\.(?:"
        + ext_group.encode("ascii")
        + rb")",
        re.IGNORECASE,
    )
    found: List[Tuple[int, str]] = []
    for m in pat.finditer(data):
        s = m.group(0).decode("ascii", errors="ignore").strip()
        if _looks_like_audio_path(s):
            found.append((m.start(), s))
    return found


def _looks_like_audio_path(s: str) -> bool:
    low = s.lower().strip()
    if not low:
        return False
    if low.endswith(".acd") or low.endswith(".acd-bak"):
        return False
    for ext in AUDIO_EXT:
        if low.endswith(ext):
            return True
    return False


def _guess_tempo_bpm(data: bytes) -> Optional[float]:
    best: Optional[float] = None
    for i in range(0, len(data) - 8, 8):
        v = struct.unpack("<d", data[i : i + 8])[0]
        if not math.isfinite(v):
            continue
        if 40 <= v <= 320 and abs(v - round(v * 4) / 4) < 1e-3:
            if best is None or (60 <= v <= 200 and (best < 60 or best > 200)):
                best = float(v)
    return best


def _guess_sample_rate_hz(data: bytes) -> Optional[int]:
    for i in range(0, len(data) - 4, 4):
        v = struct.unpack("<I", data[i : i + 4])[0]
        if v in (8000, 11025, 12000, 16000, 22050, 24000, 32000, 44100, 48000, 88200, 96000, 192000):
            return int(v)
    return None


def _dedupe_preserve(seq: Sequence[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for s in seq:
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def _resolve_clip_path(
    raw: str,
    project_file: Path,
    media_roots: Iterable[Path],
) -> Path:
    """
    Map a path string from the ACID file to a filesystem path.
    Prefer existing files under media_roots or relative to the project dir.
    """
    p = Path(raw)
    if p.is_absolute() and p.exists():
        return p
    name = p.name
    for root in media_roots:
        cand = root / name
        if cand.exists():
            return cand
        try:
            for child in root.iterdir():
                if child.is_file() and child.name.lower() == name.lower():
                    return child
        except OSError:
            pass
    here = project_file.parent / name
    if here.exists():
        return here
    return Path(raw)


def parse_acid_project(
    project_file: Path,
    raw: bytes,
    media_roots: Optional[Sequence[Path]] = None,
) -> AcidProject:
    """
    Parse ACID project bytes (classic .acd / .acd-bak, or inner file from ACD-ZIP).

    Uses version fingerprints from `acd_signatures.json` when a file matches a
    catalogued sample, then falls back to heuristics. Timeline positions, pitch,
    stretch, and FX are not fully recoverable for most variants.
    """
    fp, structured = extract_structured_fields(raw)
    scan_blob = raw
    if structured.ole_stream_bytes:
        scan_blob = raw + b"\n" + structured.ole_stream_bytes

    roots: List[Path] = list(media_roots or ())
    roots.append(project_file.parent)

    u16 = _utf16le_strings(scan_blob)
    ascii_hits = _ascii_audio_paths(scan_blob)

    path_strings: List[str] = []
    for _off, s in u16:
        if _looks_like_audio_path(s):
            path_strings.append(s.strip())
    for _off, s in ascii_hits:
        path_strings.append(s.strip())
    if structured.riff_strings:
        for s in structured.riff_strings:
            if _looks_like_audio_path(s):
                path_strings.append(s.strip())

    path_strings = _dedupe_preserve(path_strings)

    # Resolve and pick best path per basename (ACID often stores both absolute and short names).
    candidates: List[Tuple[str, Path]] = []
    for ps in path_strings:
        candidates.append((ps, _resolve_clip_path(ps, project_file, roots)))

    candidates.sort(key=lambda t: (0 if t[1].exists() else 1, len(t[0]), t[0].lower()))

    by_base: dict[str, Tuple[str, Path]] = {}
    for path_str, resolved in candidates:
        base = Path(path_str.replace("\\", "/")).name.lower()
        if not base:
            continue
        prev = by_base.get(base)
        if prev is None:
            by_base[base] = (path_str, resolved)
            continue
        prev_raw, prev_res = prev
        if resolved.exists() and not prev_res.exists():
            by_base[base] = (path_str, resolved)
        elif (
            resolved.exists()
            and prev_res.exists()
            and len(path_str) < len(prev_raw)
        ):
            by_base[base] = (path_str, resolved)

    # One track per referenced media file (typical ACID layout for loops).
    tracks: List[AcidTrack] = []
    for idx, (_ps, resolved) in enumerate(by_base.values()):
        name = resolved.stem or f"Track {idx + 1}"
        clip = AcidClip(path=resolved, position_sec=0.0, name=name)
        tracks.append(AcidTrack(name=name, clips=[clip]))

    tempo = structured.tempo_bpm or _guess_tempo_bpm(raw) or 120.0
    sr = structured.sample_rate_hz or _guess_sample_rate_hz(raw)

    notes: List[str] = [
        f"Format family: {fp.family_id}"
        + (f" (ACID Pro ~{fp.acid_pro_major_guess})" if fp.acid_pro_major_guess else ""),
        "Converted from ACID project (binary fingerprint + heuristics).",
        "Verify: tempo, clip positions, stretch, pitch, envelopes, and FX.",
    ]
    if structured.signature_id:
        notes.append(f"Matched signature record: {structured.signature_id}")
    if not tracks:
        notes.append("No audio file references were found; try opening the project in ACID and re-saving.")

    return AcidProject(
        source_path=project_file,
        tempo_bpm=tempo,
        sample_rate=sr,
        tracks=tracks,
        notes=notes,
        format_family=fp.family_id,
        format_signature_id=structured.signature_id,
        acid_pro_major_guess=fp.acid_pro_major_guess,
    )
