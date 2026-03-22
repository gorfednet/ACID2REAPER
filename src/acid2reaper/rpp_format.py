"""Small helpers for serializing values into REAPER ``.rpp`` line tokens."""

from __future__ import annotations


def format_rpp_float(value: float) -> str:
    """Format a float the way REAPER’s line-oriented chunks usually expect (no scientific notation surprises)."""
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.12g}"
