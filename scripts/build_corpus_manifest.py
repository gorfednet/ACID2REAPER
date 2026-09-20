#!/usr/bin/env python3
"""
Summarise a local folder of real ACID projects into a committable manifest.

The projects this was developed against are private music. Nothing identifying
goes into the manifest: no audio, no project bytes, no titles, and no file
paths. Each project contributes its decoded timing, its chunk-GUID inventory,
and counts -- enough to catch a decoding regression on a build generation that
nobody has a sample of any more, and not enough to reconstruct anything.

Media path *shapes* are recorded as a salted hash plus the extension, so a
regression that loses paths is still visible without publishing filenames.

    python scripts/build_corpus_manifest.py --corpus-dir ~/Music \\
        --out tests/fixtures/corpus_manifest.json
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from acid2reaper.binary.wave64 import (  # noqa: E402
    extract_acid_wave64_timeline,
    extract_timebase,
    iter_wave64_nodes,
    parse_wave64_tree,
)

PROJECT_SUFFIXES = {".acd", ".acd-bak", ".acd-zip"}
#: Fixed salt: the hashes only need to be stable and non-reversible in practice,
#: and a per-run salt would churn the manifest on every rebuild.
SALT = b"acid2reaper-corpus-v1"


def _hash(text: str) -> str:
    return hashlib.sha256(SALT + text.encode("utf-8", "replace")).hexdigest()[:16]


def _digest_tracks(timeline) -> str:
    """One hash over every decoded per-track field, in order."""
    rows = []
    for track in timeline.tracks:
        loop = track.source_loop
        rows.append(
            [
                _hash(track.media_path.lower()) if track.media_path else None,
                [[e.position_ticks, e.length_ticks] for e in track.events],
                None
                if loop is None
                else [loop.tempo_bpm, loop.beats, loop.time_sig_num, loop.time_sig_den, loop.flags],
            ]
        )
    canonical = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(SALT + canonical.encode("utf-8")).hexdigest()


def _iter_projects(corpus_dir: Path) -> Iterable[Path]:
    for path in sorted(corpus_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in PROJECT_SUFFIXES:
            yield path


def summarise(raw: bytes) -> dict | None:
    """Reduce one project to its structural fingerprint."""
    root = parse_wave64_tree(raw)
    if root is None:
        return {"parsed": False}

    # The GUID *set* is what identifies a build generation; per-file counts
    # vary with project size and add nothing a regression test can use.
    guids = sorted({str(n.guid) for n in iter_wave64_nodes(root)})
    forms = sorted({str(n.form_guid) for n in iter_wave64_nodes(root) if n.form_guid})
    timebase = extract_timebase(raw, root)
    timeline = extract_acid_wave64_timeline(raw)

    entry: dict = {
        "parsed": True,
        "size_bytes": len(raw),
        "chunk_guids": guids,
        "form_guids": forms,
        "timebase": None
        if timebase is None
        else {
            "ppq": timebase.ppq,
            "usec_per_beat": timebase.usec_per_beat,
            "tempo_bpm": timebase.tempo_bpm,
            "time_sig": [timebase.time_sig_num, timebase.time_sig_den],
        },
        "timeline": None,
    }
    if timeline is not None:
        entry["timeline"] = {
            "tempo_bpm": timeline.tempo_bpm,
            "ppq": timeline.ppq,
            "sample_rate_hz": timeline.sample_rate_hz,
            "time_sig": [timeline.time_sig_num, timeline.time_sig_den],
            "track_count": len(timeline.tracks),
            "event_count": sum(len(t.events) for t in timeline.tracks),
            "tracks_with_media": sum(1 for t in timeline.tracks if t.media_path),
            "media_suffixes": dict(
                sorted(
                    collections.Counter(
                        Path(t.media_path.replace("\\", "/")).suffix.lower()
                        for t in timeline.tracks
                        if t.media_path
                    ).items()
                )
            ),
            "source_loop_tempos": sorted(
                {t.source_loop.tempo_bpm for t in timeline.tracks if t.source_loop}
            ),
            "source_loop_flags": sorted(
                {t.source_loop.flags for t in timeline.tracks if t.source_loop}
            ),
            # Every per-track field, reduced to one hash. A change to any
            # track's media reference, event ticks or cached loop moves this,
            # so the manifest stays sensitive without carrying 2 MB of detail
            # or anything identifying.
            "tracks_digest": _digest_tracks(timeline),
        }
    return entry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--max-projects",
        type=int,
        default=0,
        help="Cap the number of projects recorded (0 = no cap).",
    )
    args = parser.parse_args()

    if not args.corpus_dir.is_dir():
        print(f"not a directory: {args.corpus_dir}", file=sys.stderr)
        return 2

    entries = []
    for path in _iter_projects(args.corpus_dir):
        if args.max_projects and len(entries) >= args.max_projects:
            break
        try:
            raw = path.read_bytes()
        except OSError as exc:
            print(f"skipping {path.name}: {exc}", file=sys.stderr)
            continue
        if not raw.startswith(b"riff"):
            continue
        summary = summarise(raw)
        summary["id"] = _hash(str(path))
        entries.append(summary)

    # Build generations repeat: a handful of distinct chunk/form GUID
    # inventories cover every project, so store each once and reference it.
    layouts: list[dict] = []
    index: dict[str, int] = {}
    for entry in entries:
        if not entry.get("parsed"):
            continue
        layout = {"chunk_guids": entry.pop("chunk_guids"), "form_guids": entry.pop("form_guids")}
        key = json.dumps(layout, sort_keys=True)
        if key not in index:
            index[key] = len(layouts)
            layouts.append(layout)
        entry["layout"] = index[key]

    entries.sort(key=lambda e: e["id"])
    manifest = {
        "schema": 1,
        "layouts": layouts,
        "boundary": (
            "Structural fingerprints only. No audio, no project bytes, no titles and no "
            "file paths are stored; media references appear as a salted hash plus the "
            "file extension."
        ),
        "project_count": len(entries),
        "projects": entries,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, indent=1, sort_keys=True)
        handle.write("\n")
    print(f"wrote {len(entries)} projects to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
