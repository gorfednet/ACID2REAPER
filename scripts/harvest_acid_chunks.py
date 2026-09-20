#!/usr/bin/env python3
"""
Harvest real ``acid`` chunk metadata from a remote disc image.

This exists to check our byte offsets against files nobody here wrote. The
committed fixture proves we can read one chunk; a few hundred chunks authored by
Sonic Foundry's own tools prove the layout itself.

**What is kept, and what is not.** The image is streamed in memory over HTTP
range requests and never written to disk. The manifest stores decoded numeric
fields -- tempo, beats, meter, flags, root note -- and a SHA-256 of each 24-byte
chunk. It stores no audio, no file names, and not the chunk bytes themselves.
Tempo, beat count and meter are unprotected facts about a recording, and a
digest of 24 bytes is a fingerprint, not a reproduction.

The digest is the point: ``tests/test_acid_chunk_corpus.py`` re-packs each
record with the shipped encoder and requires the hash to match the bytes that
were actually on the disc. A test-local reimplementation would share the
parser's assumptions and prove nothing.

    ACID2REAPER_ALLOW_NETWORK=1 python scripts/harvest_acid_chunks.py \\
        --url https://archive.org/download/free-loops/FREE_LOOPS.BIN \\
        --max-bytes 40000000 --out tests/fixtures/acid_chunk_corpus.json
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import struct
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, Iterator, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from acid2reaper.binary.acid_chunk import (  # noqa: E402
    ACID_CHUNK_BYTES,
    KNOWN_FLAGS,
    AcidChunk,
    parse_acid_chunk,
)

DOCUMENTED_URL = "https://archive.org/download/free-loops/FREE_LOOPS.BIN"
DOCUMENTED_MEDIA = "Sonic Foundry 'Free Loops 4 ACID' CD image (Internet Archive)"
WINDOW = 4 << 20
OVERLAP = 64
NOTICE = """\
This downloads parts of a third-party disc image over the network.

Only decoded chunk metadata and a digest of each 24-byte chunk are written out.
No audio, no file names and no chunk bytes are kept, and nothing is saved to
disk except the manifest. Respect the source's terms of use.
"""


def range_get(url: str, start: int, end: int, *, retries: int = 3) -> bytes:
    """Fetch ``[start, end)``. Raises if the server ignores the range header."""
    last: Exception | None = None
    for attempt in range(retries):
        request = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end - 1}"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                if response.status != 206:
                    raise RuntimeError(
                        f"server returned {response.status}, not 206: it is ignoring Range "
                        "headers, and downloading the whole image is not what this script does"
                    )
                return response.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"range request failed after {retries} attempts: {last}")


def scan_window(window: bytes) -> Iterator[Tuple[int, AcidChunk, bytes]]:
    """Yield every plausible ``acid`` chunk in a buffer."""
    offset = 0
    while True:
        offset = window.find(b"acid", offset + 1)
        if offset < 0:
            return
        body = offset + 8
        if body + ACID_CHUNK_BYTES > len(window):
            return
        try:
            size = struct.unpack_from("<I", window, offset + 4)[0]
        except struct.error:
            return
        if size != ACID_CHUNK_BYTES:
            continue
        chunk = parse_acid_chunk(window, body)
        if chunk is None:
            continue
        if chunk.flags & ~KNOWN_FLAGS:
            continue
        if not 1 <= chunk.beats <= 1_000_000:
            continue
        if not (1 <= chunk.meter_num <= 32 and 1 <= chunk.meter_den <= 32):
            continue
        yield offset, chunk, bytes(window[body : body + ACID_CHUNK_BYTES])


def harvest(url: str, *, max_bytes: int) -> Tuple[List[Dict], int]:
    records: Dict[str, Dict] = {}
    position = 0
    while position < max_bytes:
        end = min(position + WINDOW, max_bytes)
        window = range_get(url, position, end)
        if not window:
            break
        for _, chunk, raw in scan_window(window):
            digest = hashlib.sha256(raw).hexdigest()
            records.setdefault(
                digest,
                {
                    "sha256": digest,
                    "flags": chunk.flags,
                    "root_note": chunk.root_note,
                    "reserved_u16": chunk.reserved_u16,
                    "beats": chunk.beats,
                    "meter_num": chunk.meter_num,
                    "meter_den": chunk.meter_den,
                    # The exact bit pattern, so the round-trip is not at the
                    # mercy of decimal formatting.
                    "tempo_f32_bits": struct.unpack("<I", struct.pack("<f", chunk.tempo_bpm))[0],
                    "tempo_bpm": round(chunk.tempo_bpm, 6),
                },
            )
        scanned = end
        print(f"  scanned {scanned / 1e6:.1f} MB, {len(records)} distinct chunks", file=sys.stderr)
        if end >= max_bytes:
            break
        position = end - OVERLAP  # a chunk may straddle a window edge
    return sorted(records.values(), key=lambda r: r["sha256"]), position


def canonical_digest(records: List[Dict]) -> str:
    canonical = json.dumps(records, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=None, help=f"Disc image URL (documented: {DOCUMENTED_URL})")
    parser.add_argument("--max-bytes", type=int, default=40_000_000)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if os.environ.get("ACID2REAPER_ALLOW_NETWORK") != "1":
        print("refusing to use the network: set ACID2REAPER_ALLOW_NETWORK=1", file=sys.stderr)
        return 2
    url = args.url or DOCUMENTED_URL
    print(NOTICE, file=sys.stderr)
    print(f"source: {url}\n", file=sys.stderr)

    records, scanned = harvest(url, max_bytes=args.max_bytes)
    if not records:
        print("no acid chunks found", file=sys.stderr)
        return 1

    manifest = {
        "schema": 1,
        "source": {
            "url": url,
            "media": DOCUMENTED_MEDIA if url == DOCUMENTED_URL else "user-supplied",
            "bytes_scanned": args.max_bytes,
            "harvested_utc": datetime.datetime.now(datetime.timezone.utc)
            .replace(microsecond=0)
            .isoformat(),
        },
        "boundary": (
            "Decoded 'acid' chunk metadata and a SHA-256 of each 24-byte chunk only. "
            "No audio, no file contents, no file names and no raw chunk bytes from the "
            "source media are present in this repository."
        ),
        "record_count": len(records),
        "records": records,
        "records_sha256": canonical_digest(records),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, indent=1, sort_keys=True)
        handle.write("\n")
    print(f"wrote {len(records)} records to {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
