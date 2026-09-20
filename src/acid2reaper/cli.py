"""
Command-line interface for **ACID2Reaper** — first public beta (ACID projects to Cockos REAPER).

The CLI is intentionally thin: validation and I/O limits live in
:mod:`acid2reaper.security`, parsing in :mod:`acid2reaper.scan`, and writing
in :mod:`acid2reaper.export_rpp`. That keeps this file easy to audit for
security reviews.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Callable, Optional, Sequence

from . import __version__, __version_label__
from .binary.meter import DEN_NUM, LEGAL_DENOMINATORS, MAX_NUMERATOR, NUM_DEN
from .containers import sniff_project_bytes
from .exceptions import Acid2ReaperError
from .export_rpp import write_rpp
from .scan import parse_acid_project
from .security import safe_output_path, validate_is_dir, validate_user_path


def _build_parser() -> argparse.ArgumentParser:
    """Configure argparse with grouped options and helpful epilog text."""
    p = argparse.ArgumentParser(
        prog="acid2reaper",
        description=(
            "Convert ACID project files (.acd, .acd-bak, .acd-zip) to Cockos REAPER (.rpp). "
            "Parsing is heuristic for proprietary formats—always verify in REAPER."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Environment safety limits (optional overrides):\n"
            "  ACID2REAPER_MAX_PROJECT_MB           — max .acd file size to read (default 256)\n"
            "  ACID2REAPER_MAX_ZIP_MEMBERS          — max files inside ACD-ZIP (default 4096)\n"
            "  ACID2REAPER_MAX_ZIP_UNCOMPRESSED_MB  — max total uncompressed ZIP (default 2048)\n"
        ),
    )
    p.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__} ({__version_label__})",
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print debug details to stderr.",
    )
    p.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Only print errors; suppress the output path on success.",
    )
    p.add_argument(
        "--gui",
        action="store_true",
        help="Open the graphical window (Tkinter) instead of running a one-shot conversion.",
    )
    p.add_argument(
        "input",
        nargs="?",
        type=Path,
        help="ACID project file (.acd, .acd-bak, or .acd-zip)",
    )
    p.add_argument(
        "output",
        nargs="?",
        type=Path,
        help="Output .rpp path (default: same base name as input)",
    )
    p.add_argument(
        "--media-dir",
        type=Path,
        action="append",
        default=[],
        metavar="DIR",
        help="Extra folder to search for audio files (repeatable).",
    )
    p.add_argument(
        "--time-sig-order",
        choices=[DEN_NUM, NUM_DEN],
        default=DEN_NUM,
        help=(
            "Slot order for ACID's raw time-signature pair. Only matters when "
            "both halves are powers of two (4/4, 4/8); 3/4, 5/4, 6/8 and 7/8 "
            "resolve themselves. Default: %(default)s."
        ),
    )
    p.add_argument(
        "--time-sig",
        metavar="NUM/DEN",
        default=None,
        help="Override the decoded time signature entirely, e.g. --time-sig 6/8.",
    )
    return p


def _parse_time_sig(value: str) -> tuple[int, int]:
    """Parse a NUM/DEN override, rejecting anything REAPER would not accept."""
    text = value.strip()
    if "/" not in text:
        raise Acid2ReaperError(f"--time-sig expects NUM/DEN, got {value!r}")
    num_text, _, den_text = text.partition("/")
    try:
        num, den = int(num_text), int(den_text)
    except ValueError:
        raise Acid2ReaperError(f"--time-sig expects NUM/DEN, got {value!r}") from None
    if not 1 <= num <= MAX_NUMERATOR:
        raise Acid2ReaperError(f"--time-sig numerator must be 1..{MAX_NUMERATOR}, got {num}")
    if den not in LEGAL_DENOMINATORS:
        allowed = ", ".join(str(d) for d in sorted(LEGAL_DENOMINATORS))
        raise Acid2ReaperError(f"--time-sig denominator must be one of {allowed}, got {den}")
    return (num, den)


def convert(
    input_path: Path,
    output_path: Path | None = None,
    extra_media_dirs: list[Path] | None = None,
    *,
    meter_order: str = DEN_NUM,
    time_sig_override: tuple[int, int] | None = None,
    on_notes: Callable[[Sequence[str]], None] | None = None,
) -> Path:
    """
    Run the full pipeline: validate paths, load bytes, parse, write .rpp.

    Raises :class:`Acid2ReaperError` subclasses on user-fixable problems so UIs
    can show a single message without a traceback.
    """
    in_safe = validate_user_path(Path(input_path), must_exist=True, must_be_file=True)

    if output_path is None:
        out = safe_output_path(in_safe.with_suffix(".rpp"), default_parent=in_safe.parent)
    else:
        out = safe_output_path(Path(output_path), default_parent=in_safe.parent)

    roots: list[Path] = []
    for d in extra_media_dirs or []:
        roots.append(validate_is_dir(Path(d)))

    raw, media_root, project_file = sniff_project_bytes(in_safe)
    roots.append(Path(media_root))

    project = parse_acid_project(
        project_file,
        raw,
        roots,
        meter_order=meter_order,
        time_sig_override=time_sig_override,
    )
    write_rpp(project, out)
    if on_notes is not None:
        on_notes(project.notes)
    return out


def main(argv: Optional[list[str]] = None) -> int:
    """Parse argv, configure logging, run conversion or GUI, return exit code."""
    args = _build_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )
    log = logging.getLogger("acid2reaper")

    if args.gui:
        try:
            from .ui.desktop import run_app
        except ImportError as exc:
            print(
                "acid2reaper: Tkinter is not available (install python3-tk or use CLI without --gui).",
                file=sys.stderr,
            )
            log.debug("GUI import failed", exc_info=exc)
            return 1
        return run_app()

    if not args.input:
        _build_parser().print_help()
        print("\nacid2reaper: error: the following arguments are required: input", file=sys.stderr)
        return 2

    def report_notes(notes: Sequence[str]) -> None:
        for note in notes:
            print(f"acid2reaper: {note}", file=sys.stderr)

    try:
        time_sig = _parse_time_sig(args.time_sig) if args.time_sig else None
        out = convert(
            args.input,
            args.output,
            extra_media_dirs=args.media_dir,
            meter_order=args.time_sig_order,
            time_sig_override=time_sig,
            on_notes=report_notes if args.verbose else None,
        )
    except Acid2ReaperError as exc:
        log.debug("Conversion failed", exc_info=True)
        print(f"acid2reaper: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        log.exception("Unexpected failure")
        print(f"acid2reaper: internal error: {exc}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
