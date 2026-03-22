"""
Input validation and safe I/O boundaries.

This tool only ever reads local project files and writes a local .rpp. There is
no network server, but we still harden against:

- **Zip bombs** (tiny archives that expand to huge data)
- **Zip slip** (archives that try to write outside the target directory)
- **Decompression exhaustion** (reading multi‑gigabyte “projects” into RAM)
- **Path tricks** (NUL bytes, odd Unicode, absurdly long paths)

Limits are conservative defaults; power users can raise them via environment
variables (see constants below).
"""

from __future__ import annotations

import os
from pathlib import Path

from .exceptions import ProjectTooLargeError, SecurityError

# ---------------------------------------------------------------------------
# Tunable limits (bytes / counts). Override via environment for large sessions.
# ---------------------------------------------------------------------------
_ENV = os.environ

# Maximum .acd / .acd-bak file read into memory in one shot.
MAX_PROJECT_BYTES = int(_ENV.get("ACID2REAPER_MAX_PROJECT_MB", "256")) * 1024 * 1024

# ZIP: refuse archives with more than this many file entries (pathological trees).
MAX_ZIP_MEMBERS = int(_ENV.get("ACID2REAPER_MAX_ZIP_MEMBERS", "4096"))

# ZIP: sum of declared *uncompressed* sizes must stay below this (zip bomb guard).
MAX_ZIP_UNCOMPRESSED_BYTES = int(_ENV.get("ACID2REAPER_MAX_ZIP_UNCOMPRESSED_MB", "2048")) * 1024 * 1024

# Reject single path components longer than this (DoS via huge filenames).
MAX_PATH_COMPONENT_LENGTH = int(_ENV.get("ACID2REAPER_MAX_PATH_COMPONENT", "512"))

# Reject full path strings longer than this after resolve.
MAX_CANONICAL_PATH_LENGTH = int(_ENV.get("ACID2REAPER_MAX_PATH_LEN", "4096"))


def _reject_dangerous_path_chars(path: Path) -> None:
    """
    Block NUL and other control characters that can confuse shells or APIs.

    We use str(path) because pathlib may preserve odd Unicode; control chars
    below 0x20 are almost never legitimate in user-chosen music project paths.
    """
    s = str(path)
    if "\x00" in s:
        raise SecurityError("Path contains a NUL byte; refusing to use it.")
    if any(ord(ch) < 32 for ch in s):
        raise SecurityError("Path contains control characters; refusing to use it.")


def validate_is_dir(path: Path) -> Path:
    """Ensure `path` exists and is a directory (for optional --media-dir roots)."""
    _reject_dangerous_path_chars(path)
    try:
        resolved = path.expanduser().resolve(strict=True)
    except FileNotFoundError as exc:
        raise SecurityError("Directory does not exist.") from exc
    except OSError as exc:
        raise SecurityError(f"Cannot resolve directory: {exc}") from exc
    if len(str(resolved)) > MAX_CANONICAL_PATH_LENGTH:
        raise SecurityError("Path exceeds maximum allowed length.")
    if not resolved.is_dir():
        raise SecurityError("Expected a directory.")
    return resolved


def validate_user_path(path: Path, *, must_exist: bool, must_be_file: bool) -> Path:
    """
    Resolve a user-supplied path safely and return a canonical Path.

    Symlinks are resolved once so the rest of the pipeline works on real paths.
    Raises SecurityError if the path looks abusive or cannot be normalized.
    """
    _reject_dangerous_path_chars(path)
    try:
        resolved = path.expanduser().resolve(strict=False)
    except OSError as exc:
        raise SecurityError(f"Cannot resolve path: {exc}") from exc
    if len(str(resolved)) > MAX_CANONICAL_PATH_LENGTH:
        raise SecurityError("Path exceeds maximum allowed length.")
    for part in resolved.parts:
        if len(part) > MAX_PATH_COMPONENT_LENGTH:
            raise SecurityError("A path component is too long.")
    if must_exist and not resolved.exists():
        raise SecurityError("Path does not exist.")
    if must_be_file and resolved.exists() and not resolved.is_file():
        raise SecurityError("Expected a regular file.")
    return resolved


def read_file_prefix(path: Path, max_bytes: int) -> bytes:
    """Read up to max_bytes from the start of a file (cheap header sniff)."""
    safe = validate_user_path(path, must_exist=True, must_be_file=True)
    with safe.open("rb") as fp:
        return fp.read(max_bytes)


def read_project_bytes_capped(path: Path) -> bytes:
    """
    Read a project file with a hard size cap to avoid memory exhaustion.

    Call this instead of Path.read_bytes() for untrusted .acd inputs.
    """
    safe = validate_user_path(path, must_exist=True, must_be_file=True)
    size = safe.stat().st_size
    if size > MAX_PROJECT_BYTES:
        raise ProjectTooLargeError(
            f"Project file is {size} bytes; maximum allowed is {MAX_PROJECT_BYTES} bytes "
            f"(set ACID2REAPER_MAX_PROJECT_MB to raise the cap)."
        )
    with safe.open("rb") as fp:
        return fp.read()


def safe_output_path(candidate: Path, default_parent: Path | None = None) -> Path:
    """
    Prepare an output .rpp path: resolve, validate characters, ensure parent exists.

    We do not force the output to live next to the input (users may want /tmp),
    but we do reject obvious nonsense.
    """
    _reject_dangerous_path_chars(candidate)
    out = candidate.expanduser()
    if not out.is_absolute():
        base = default_parent or Path.cwd()
        out = (base / out).resolve()
    else:
        out = out.resolve()
    if len(str(out)) > MAX_CANONICAL_PATH_LENGTH:
        raise SecurityError("Output path is too long.")
    for part in out.parts:
        if len(part) > MAX_PATH_COMPONENT_LENGTH:
            raise SecurityError("Output path has a component that is too long.")
    return out


def sanitize_rpp_file_token(path: Path) -> str:
    """
    Produce a string safe to embed in REAPER's RPP FILE line.

    REAPER accepts quoted paths; we strip control characters so the project
    file stays valid text and cannot hide escape sequences from naive tools.
    """
    raw = str(path.expanduser().resolve(strict=False))
    # Remove ASCII control chars except tab (unlikely in paths)
    cleaned = "".join(ch for ch in raw if ord(ch) >= 32 or ch in "\t")
    if "\x00" in cleaned:
        cleaned = cleaned.replace("\x00", "")
    return cleaned


# Optional: detect block devices (Unix) — writing “.rpp” to /dev/null is fine for tests;
# we allow it. Blocking raw devices is niche; skip for portability.
