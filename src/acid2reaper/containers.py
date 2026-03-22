"""
Project containers: plain .acd bytes vs ACD-ZIP bundles.

ACD-ZIP is a normal ZIP file. Archives must never be trusted: we cap member
counts and total uncompressed size before extraction, and we block path
traversal (zip slip) the same way server-side unzip utilities do.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Tuple

from .exceptions import SecurityError, ZipBombError
from .security import (
    MAX_ZIP_MEMBERS,
    MAX_ZIP_UNCOMPRESSED_BYTES,
    read_file_prefix,
    read_project_bytes_capped,
    validate_user_path,
)

AUDIO_EXT = frozenset(
    {
        ".wav",
        ".wave",
        ".aif",
        ".aiff",
        ".afc",
        ".mp3",
        ".flac",
        ".ogg",
        ".oga",
        ".wma",
        ".m4a",
        ".aac",
        ".rex",
    }
)


def is_acd_zip(path: Path, head: bytes) -> bool:
    """True if the file is likely an ACD-ZIP (by extension or PK header)."""
    if path.suffix.lower() in (".acd-zip", ".acdzip"):
        return True
    return len(head) >= 4 and head[:4] == b"PK\x03\x04"


def _zip_preflight(zf: zipfile.ZipFile) -> None:
    """
    Reject archives that look like zip bombs or abuse patterns.

    We sum *declared* uncompressed sizes (pre-decompression). That is cheap
    and catches the classic “4 GB of zeros compressed to 40 KB” attack.
    """
    members = zf.infolist()
    if len(members) > MAX_ZIP_MEMBERS:
        raise ZipBombError(
            f"Too many files in archive ({len(members)}); "
            f"maximum is {MAX_ZIP_MEMBERS}."
        )
    total = 0
    for m in members:
        # Zip64 can report -1 for unknown sizes; treat as max risk and skip sum.
        if m.file_size < 0:
            raise ZipBombError("ZIP entry has invalid size metadata.")
        total += m.file_size
        if total > MAX_ZIP_UNCOMPRESSED_BYTES:
            raise ZipBombError(
                "ZIP uncompressed size exceeds safety limit "
                f"({MAX_ZIP_UNCOMPRESSED_BYTES} bytes). "
                "Set ACID2REAPER_MAX_ZIP_UNCOMPRESSED_MB if you trust this file."
            )


def _assert_zip_member_safe(dest_resolved: Path, member: zipfile.ZipInfo) -> None:
    """Ensure extracting `member` cannot escape `dest_resolved` (zip slip)."""
    target = (dest_resolved / member.filename).resolve()
    try:
        target.relative_to(dest_resolved)
    except ValueError as exc:
        raise SecurityError(
            f"Unsafe path in ACD-ZIP archive: {member.filename!r}"
        ) from exc


def extract_acd_zip(zpath: Path) -> Tuple[Path, Path]:
    """
    Unpack ACD-ZIP next to the archive into a dedicated folder.

    Returns (inner_acd_path, media_root_dir). Only the first *.acd found is used;
    multi-project archives are rare; callers can extend this later.
    """
    zpath = validate_user_path(zpath, must_exist=True, must_be_file=True)
    dest = zpath.parent / (zpath.stem + "_acd_extracted")
    dest.mkdir(parents=True, exist_ok=True)
    dest_resolved = dest.resolve()

    with zipfile.ZipFile(zpath, "r") as zf:
        _zip_preflight(zf)
        for member in zf.infolist():
            _assert_zip_member_safe(dest_resolved, member)
        zf.extractall(dest)

    acd_files = sorted(dest.glob("*.acd")) + sorted(dest.glob("*.ACD"))
    if not acd_files:
        raise ValueError(f"No .acd project found inside ACD-ZIP: {zpath}")
    inner = acd_files[0]
    return inner, dest


def sniff_project_bytes(path: Path) -> Tuple[bytes, Path, Path]:
    """
    Load raw project bytes. If the input is ACD-ZIP, extract first and read inner .acd.

    Returns:
        (project_bytes, media_search_root, project_file_path)

    `project_file_path` is the .acd path used for relative media resolution
    (the extracted inner file when starting from a ZIP).
    """
    path = validate_user_path(path, must_exist=True, must_be_file=True)
    head = read_file_prefix(path, 16)
    if is_acd_zip(path, head):
        inner, root = extract_acd_zip(path)
        return read_project_bytes_capped(inner), root, inner
    data = read_project_bytes_capped(path)
    return data, path.parent, path
