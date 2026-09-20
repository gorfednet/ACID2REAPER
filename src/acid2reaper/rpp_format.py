"""Small helpers for serializing values into REAPER ``.rpp`` line tokens."""

from __future__ import annotations

import math


def format_rpp_float(value: float) -> str:
    """
    Format a float for a REAPER line token.

    REAPER's chunk parser reads plain decimals. ``%g`` is compact and is what
    the rest of the file looks like, but it switches to scientific notation for
    extreme magnitudes, which REAPER does not understand -- a clip written as
    ``POSITION 3.1e+14`` is silently misread. Fall back to fixed notation in
    exactly those cases, so ordinary values keep their familiar form.
    """
    if not math.isfinite(value):
        return "0"
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    text = f"{value:.12g}"
    if "e" in text or "E" in text:
        text = f"{value:.12f}".rstrip("0").rstrip(".")
    return text or "0"
