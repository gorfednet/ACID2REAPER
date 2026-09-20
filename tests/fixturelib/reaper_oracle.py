"""
Use a local REAPER install as ground truth for generated projects.

Round-tripping through the ``rpp`` library only proves our own writer and reader
agree. This asks REAPER itself: load a generated project, save it back, and
compare what REAPER understood against what we wrote.

Opt in with ``ACID2REAPER_REAPER_ORACLE=1``. It is skipped by default and in CI,
which has no REAPER, no licence and no display.

**Attended, not unattended.** An unlicensed REAPER shows an evaluation nag at
startup that does not dismiss itself, so a run may sit waiting for a click. The
harness polls for its output with a generous timeout and says so when it gives
up, rather than hanging without explanation. UI-automating that dialog would be
brittle, platform-specific, and would break on any REAPER redesign.
"""

from __future__ import annotations

import os
import shlex
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rpp import loads
from rpp.element import Element

DEFAULT_BINARIES = {
    "darwin": Path("/Applications/REAPER.app/Contents/MacOS/REAPER"),
    "win32": Path(r"C:\Program Files\REAPER (x64)\reaper.exe"),
    "linux": Path("/opt/REAPER/reaper"),
}
DEFAULT_TIMEOUT = float(os.environ.get("ACID2REAPER_REAPER_TIMEOUT", "120"))


class ReaperOracleTimeout(RuntimeError):
    """REAPER produced no output before the deadline, most likely a modal dialog."""


def reaper_binary() -> Optional[Path]:
    """Locate REAPER: explicit override, then the platform default, then PATH."""
    override = os.environ.get("ACID2REAPER_REAPER_BIN")
    if override:
        candidate = Path(override).expanduser()
        return candidate if candidate.exists() else None
    default = DEFAULT_BINARIES.get(sys.platform)
    if default is not None and default.exists():
        return default
    found = shutil.which("reaper") or shutil.which("REAPER")
    return Path(found) if found else None


def sandbox_dir() -> Path:
    """
    A throwaway REAPER resource directory.

    Kept between runs rather than created per test: a fresh directory makes
    REAPER rescan plug-ins and reconfigure audio, which is slow and is itself a
    source of dialogs. Seeded once from the user's own reaper.ini so audio
    settings carry over, but never written back to.
    """
    base = Path(os.environ.get("ACID2REAPER_REAPER_SANDBOX", Path.home() / ".cache" / "acid2reaper" / "reaper-oracle"))
    base.mkdir(parents=True, exist_ok=True)
    config = base / "reaper.ini"
    if not config.exists():
        for source in (
            Path.home() / "Library" / "Application Support" / "REAPER" / "reaper.ini",
            Path.home() / ".config" / "REAPER" / "reaper.ini",
        ):
            if source.exists():
                shutil.copy(source, config)
                break
        else:
            config.write_text("[REAPER]\n", encoding="utf-8")
    return base


def _terminate(process: subprocess.Popen) -> None:
    """
    Always kill REAPER rather than negotiating a clean exit.

    The sandbox config is disposable and nothing is saved, so killing it is safe
    and removes every save-on-quit prompt.
    """
    if process.poll() is not None:
        return
    try:
        if hasattr(os, "killpg"):
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        else:
            process.terminate()
        process.wait(timeout=5)
    except (ProcessLookupError, PermissionError, subprocess.TimeoutExpired, OSError):
        try:
            process.kill()
        except OSError:
            pass


def _run_until_file(argv: List[str], sentinel: Path, timeout: float) -> Path:
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(
        argv,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            if sentinel.exists() and sentinel.stat().st_size > 0:
                time.sleep(0.3)  # let REAPER finish writing
                return sentinel
            if process.poll() is not None and sentinel.exists():
                return sentinel
            time.sleep(0.25)
        raise ReaperOracleTimeout(
            f"REAPER produced no output within {timeout:.0f}s.\n"
            f"  command: {shlex.join(argv)}\n"
            "  Most likely a modal dialog is waiting. This REAPER install has no "
            "licence file, so it shows an evaluation nag at startup; dismiss it and "
            "re-run, or raise ACID2REAPER_REAPER_TIMEOUT."
        )
    finally:
        _terminate(process)


def reaper_normalize(rpp_in: Path, *, timeout: float = DEFAULT_TIMEOUT) -> Path:
    """Have REAPER load a project and save it back, and return the saved copy."""
    binary = reaper_binary()
    if binary is None:
        raise RuntimeError("no REAPER binary found; set ACID2REAPER_REAPER_BIN")

    sandbox = sandbox_dir()
    out = sandbox / "normalized" / f"{rpp_in.stem}.normalized.rpp"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    argv = [
        str(binary),
        "-cfgfile",
        str(sandbox / "reaper.ini"),
        "-nosplash",
        "-noactivate",
        "-newinst",
        "-ignoreerrors",
        str(rpp_in),
        "-saveas",
        str(out),
        "-close:nosave:exit",
    ]
    return _run_until_file(argv, out, timeout)


@dataclass(frozen=True)
class RppProjection:
    """The parts of a project worth comparing between our writer and REAPER's."""

    tempo: float
    time_sig: Tuple[int, int]
    track_names: Tuple[str, ...]
    items: Tuple[Tuple[str, float, float, float, float, str], ...]


def _lines(element: Element, tag: str) -> List[list]:
    return [c for c in element.children if isinstance(c, list) and c and c[0] == tag]


def _children(element: Element, tag: str) -> List[Element]:
    return [c for c in element.children if isinstance(c, Element) and c.tag == tag]


def _first(element: Element, tag: str, default: Optional[str] = None) -> Optional[str]:
    found = _lines(element, tag)
    return found[0][1] if found and len(found[0]) > 1 else default


def project_rpp(text: str) -> RppProjection:
    """Reduce a project file to its musically meaningful content."""
    root = loads(text)
    # REAPER writes its own trailing fields (TEMPO 140 7 8 0), so read by
    # position rather than unpacking a fixed width.
    tempo_line = _lines(root, "TEMPO")[0]
    tempo, num, den = tempo_line[1], tempo_line[2], tempo_line[3]

    names: List[str] = []
    items: List[Tuple[str, float, float, float, float, str]] = []
    for index, track in enumerate(_children(root, "TRACK")):
        name = _first(track, "NAME", "") or ""
        if index == 0 and not name:
            continue  # master bus
        names.append(name)
        for item in _children(track, "ITEM"):
            sources = _children(item, "SOURCE")
            file_token = _first(sources[0], "FILE", "") if sources else ""
            playrate = _lines(item, "PLAYRATE")
            items.append(
                (
                    name,
                    float(_first(item, "POSITION", "0")),
                    float(_first(item, "LENGTH", "0")),
                    float(_first(item, "SOFFS", "0")),
                    float(playrate[0][1]) if playrate and len(playrate[0]) > 1 else 1.0,
                    Path((file_token or "").replace("\\", "/")).name.lower(),
                )
            )
    return RppProjection(float(tempo), (int(num), int(den)), tuple(names), tuple(items))


def compare_with_reaper(
    ours: Path,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    tolerance: float = 1e-6,
) -> Dict[str, List[str]]:
    """
    Compare our project against REAPER's own re-save of it.

    Returns a mapping of field name to human-readable differences; an empty
    mapping means REAPER understood everything we wrote. Only the projection is
    compared: REAPER rewrites the whole document and fills in dozens of defaults,
    so asserting on raw text would fail on formatting alone.
    """
    theirs_path = reaper_normalize(ours, timeout=timeout)
    mine = project_rpp(ours.read_text(encoding="utf-8"))
    theirs = project_rpp(theirs_path.read_text(encoding="utf-8"))

    differences: Dict[str, List[str]] = {}
    if abs(mine.tempo - theirs.tempo) > tolerance:
        differences["tempo"] = [f"ours={mine.tempo} reaper={theirs.tempo}"]
    if mine.time_sig != theirs.time_sig:
        differences["time_sig"] = [f"ours={mine.time_sig} reaper={theirs.time_sig}"]
    if mine.track_names != theirs.track_names:
        differences["track_names"] = [f"ours={mine.track_names} reaper={theirs.track_names}"]

    if len(mine.items) != len(theirs.items):
        differences["item_count"] = [f"ours={len(mine.items)} reaper={len(theirs.items)}"]
        return differences

    item_diffs: List[str] = []
    for index, (a, b) in enumerate(zip(mine.items, theirs.items)):
        for field, x, y in zip(("position", "length", "soffs", "playrate"), a[1:5], b[1:5]):
            if abs(x - y) > tolerance:
                item_diffs.append(f"item {index} {field}: ours={x} reaper={y}")
        if a[5] != b[5]:
            item_diffs.append(f"item {index} source: ours={a[5]} reaper={b[5]}")
    if item_diffs:
        differences["items"] = item_diffs
    return differences
