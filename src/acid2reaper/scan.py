"""
Turn raw ACID project bytes into our neutral :class:`AcidProject` model (**ACID2Reaper**).

The pipeline is deliberately split into small steps so newcomers can follow it:

1. **Parse** the GUID-chunked Wave64 tree when the catalogued ACID layout is
   present, including project timing and event positions.
2. **Fingerprint** other binaries (:mod:`acid2reaper.binary.extract`) to pull tempo /
   sample rate when we recognize the layout.
3. **Scan** for path-like strings (UTF-16 Windows paths are common; ASCII paths
   appear in some builds).
4. **Resolve** each string to a real filesystem path next to the project or
   under optional media folders.
5. **Build tracks**—one track per unique audio basename, which matches many
   simple ACID loop projects (not every complex session).

Undecoded fields are deliberately left at neutral defaults. Complex automation
envelopes and unverified mix/edit parameters are not exported.
"""

from __future__ import annotations

import math
import re
import struct
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

from .acid_routing import collect_plugin_and_bus_hints
from .binary.extract import extract_structured_fields
from .binary.wave64 import extract_acid_wave64_timeline
from .containers import AUDIO_EXT
from .model import PLAYRATE_MAX, PLAYRATE_MIN, AcidClip, AcidProject, AcidTrack, MasterBus
from .string_scan import utf16le_ascii_runs


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


def _source_playrate(project_tempo: float, source_tempo: Optional[float]) -> float:
    """
    Stretch factor that beat-maps a source loop onto the project tempo.

    ACID caches the source loop's own tempo per track, so a loop authored at
    139.56 BPM inside a 120 BPM project plays back at 120/139.56. Missing or
    implausible values leave the clip unstretched.
    """
    if source_tempo is None or not math.isfinite(source_tempo) or source_tempo <= 0.0:
        return 1.0
    if not math.isfinite(project_tempo) or project_tempo <= 0.0:
        return 1.0
    rate = project_tempo / source_tempo
    if not PLAYRATE_MIN <= rate <= PLAYRATE_MAX:
        return 1.0
    return rate


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

    Unresolved basenames are anchored to the project directory (never the
    process CWD), so REAPER ``FILE`` tokens stay next to the ``.acd``.
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
    # Keep a project-relative path even when the media file is missing so
    # sanitize_rpp_file_token does not resolve a bare basename against CWD.
    if p.is_absolute():
        return p
    return project_file.parent / name


def parse_acid_project(
    project_file: Path,
    raw: bytes,
    media_roots: Optional[Sequence[Path]] = None,
) -> AcidProject:
    """
    Parse ACID project bytes (classic .acd / .acd-bak, or inner file from ACD-ZIP).

    Uses the catalogued Wave64 ACID layout for event timing, then version
    fingerprints from `acd_signatures.json` and conservative heuristics for
    formats whose event structure is still unknown.
    """
    fp, structured = extract_structured_fields(raw)
    scan_blob = raw
    if structured.ole_stream_bytes:
        scan_blob = raw + b"\n" + structured.ole_stream_bytes

    roots: List[Path] = list(media_roots or ())
    roots.append(project_file.parent)

    u16 = utf16le_ascii_runs(scan_blob)
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

    wave64_timeline = extract_acid_wave64_timeline(raw)
    tempo = (
        wave64_timeline.tempo_bpm
        if wave64_timeline is not None
        else structured.tempo_bpm or _guess_tempo_bpm(raw) or 120.0
    )
    sr = (
        wave64_timeline.sample_rate_hz
        if wave64_timeline is not None and wave64_timeline.sample_rate_hz
        else structured.sample_rate_hz or _guess_sample_rate_hz(raw)
    )

    tracks: List[AcidTrack] = []
    if wave64_timeline is not None:
        seconds_per_tick = 60.0 / (tempo * wave64_timeline.ppq)
        fallback_media = next(iter(by_base.values()), (None, project_file.parent / "missing.wav"))[1]
        for idx, event_track in enumerate(wave64_timeline.tracks):
            if event_track.media_path:
                resolved = _resolve_clip_path(event_track.media_path, project_file, roots)
            else:
                resolved = fallback_media
            name = resolved.stem or f"Track {idx + 1}"
            source_loop = event_track.source_loop
            playrate = _source_playrate(
                tempo, source_loop.tempo_bpm if source_loop is not None else None
            )
            clips = [
                AcidClip(
                    path=resolved,
                    position_sec=event.position_ticks * seconds_per_tick,
                    length_sec=event.length_ticks * seconds_per_tick,
                    name=name,
                    playrate=playrate,
                )
                for event in event_track.events
            ]
            tracks.append(AcidTrack(name=name, clips=clips))
    else:
        # Fallback for uncatalogued variants: one neutral clip per media reference.
        for idx, (_ps, resolved) in enumerate(by_base.values()):
            name = resolved.stem or f"Track {idx + 1}"
            clip = AcidClip(path=resolved, position_sec=0.0, name=name)
            tracks.append(AcidTrack(name=name, clips=[clip]))

    source_tempos = sorted(
        {
            track.source_loop.tempo_bpm
            for track in (wave64_timeline.tracks if wave64_timeline is not None else ())
            if track.source_loop is not None
        }
    )

    notes: List[str] = [
        f"Format family: {fp.family_id}"
        + (f" (ACID Pro ~{fp.acid_pro_major_guess})" if fp.acid_pro_major_guess else ""),
        "Converted from ACID project (binary fingerprint + heuristics).",
        (
            "Timeline positions and lengths extracted from catalogued Wave64 ACID events."
            if wave64_timeline is not None
            else "WARNING: event layout is not catalogued for this format; media references start at 0:00."
        ),
    ]
    if wave64_timeline is not None:
        notes.append(
            (
                "Clip stretch (PLAYRATE, pitch preserved) derived from cached source "
                "loop tempo: " + ", ".join(f"{bpm:g} BPM" for bpm in source_tempos[:8])
            )
            if source_tempos
            else "No cached source loop tempo found; clip stretch left at 1.0."
        )
    notes.append("Verify: tempo, clip positions, stretch, pitch, envelopes, and FX.")

    proj = AcidProject(
        source_path=project_file,
        tempo_bpm=tempo,
        time_sig_num=(
            wave64_timeline.time_sig_num
            if wave64_timeline is not None and wave64_timeline.time_sig_num
            else 4
        ),
        time_sig_den=(
            wave64_timeline.time_sig_den
            if wave64_timeline is not None and wave64_timeline.time_sig_den
            else 4
        ),
        sample_rate=sr,
        master=MasterBus(),
        tracks=tracks,
        notes=notes,
        format_family=fp.family_id,
        format_signature_id=structured.signature_id,
        acid_pro_major_guess=fp.acid_pro_major_guess,
    )
    hints = collect_plugin_and_bus_hints(scan_blob)
    if hints:
        proj.unmapped_plugin_hints.extend(hints)
        proj.notes.append(
            "Mixer hints (FX/busses/groups—strings only; REAPER needs FXID to load plug-ins): "
            + "; ".join(hints[:12])
            + ("…" if len(hints) > 12 else "")
        )
    if structured.signature_id:
        proj.notes.append(f"Matched signature record: {structured.signature_id}")
    if not tracks:
        proj.notes.append(
            "No audio file references were found; try opening the project in ACID and re-saving."
        )
    missing = [
        str(clip.path)
        for track in tracks
        for clip in track.clips
        if not clip.path.exists()
    ]
    if missing:
        proj.notes.append(
            "WARNING: media not found on disk (FILE paths are still project-relative; "
            "pass --media-dir or place WAV/AIFF next to the .acd): "
            + "; ".join(missing[:8])
            + ("…" if len(missing) > 8 else "")
        )

    return proj
