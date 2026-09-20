"""
Read audio duration from disk using only the Python standard library.

We only need rough clip lengths for REAPER items. If the format is unknown or
the file is missing, callers fall back to a default length in the exporter.
"""

from __future__ import annotations

import wave
from pathlib import Path
from typing import Optional

try:  # pragma: no cover - availability depends on the interpreter version
    import aifc
except ImportError:
    # ``aifc`` was removed in Python 3.13 (PEP 594). AIFF durations are then
    # unavailable, but importing this module must never break the CLI.
    aifc = None  # type: ignore[assignment]

_AIFF_ERRORS: tuple = (OSError, wave.Error) if aifc is None else (OSError, wave.Error, aifc.Error)


def media_length_seconds(path: Path) -> Optional[float]:
    """Return duration in seconds for common formats (stdlib only)."""
    suf = path.suffix.lower()
    try:
        if suf == ".wav":
            with wave.open(str(path), "rb") as w:
                frames = w.getnframes()
                rate = w.getframerate()
                if rate <= 0:
                    return None
                return frames / float(rate)
        if suf in (".aif", ".aiff"):
            if aifc is None:
                return None
            with aifc.open(str(path), "rb") as w:
                frames = w.getnframes()
                rate = w.getframerate()
                if rate <= 0:
                    return None
                return frames / float(rate)
    except _AIFF_ERRORS:
        return None
    return None
