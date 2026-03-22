"""
Read audio duration from disk using only the Python standard library.

We only need rough clip lengths for REAPER items. If the format is unknown or
the file is missing, callers fall back to a default length in the exporter.
"""

from __future__ import annotations

import aifc
import wave
from pathlib import Path
from typing import Optional


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
            with aifc.open(str(path), "rb") as w:
                frames = w.getnframes()
                rate = w.getframerate()
                if rate <= 0:
                    return None
                return frames / float(rate)
    except (OSError, wave.Error, aifc.Error):
        return None
    return None
