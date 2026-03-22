"""
Build a REAPER `.rpp` document tree and write UTF-8 text (ACID2Reaper output).

REAPER projects are line-oriented; we only emit what is needed for a basic
import. File paths are passed through :func:`sanitize_rpp_file_token` so
control characters cannot break parsing or confuse downstream tools.
"""

from __future__ import annotations

from pathlib import Path

from rpp import dumps
from rpp.element import Element

from .media_duration import media_length_seconds
from .model import AcidProject
from .security import sanitize_rpp_file_token


def _source_tag(path: Path) -> tuple:
    """Pick the REAPER SOURCE subtype from the file extension (WAVE, MP3, …)."""
    suf = path.suffix.lower()
    if suf == ".mp3":
        return ("MP3",)
    if suf in (".ogg", ".oga"):
        return ("VORBIS",)
    if suf == ".flac":
        return ("FLAC",)
    return ("WAVE",)


def _line(*tokens: str) -> list:
    """One RPP line as a list of tokens (what the `rpp` library expects)."""
    return list(tokens)


def acid_project_to_rpp(project: AcidProject) -> Element:
    """
    Turn our normalized :class:`AcidProject` into the root `REAPER_PROJECT` element.

    Missing optional chunks are fine—REAPER fills defaults when opening the file.
    """
    root = Element("REAPER_PROJECT", ("0.1", "6.0", "0"))
    root.children.extend(
        [
            _line("RIPPLE", "0"),
            _line("GROUPOVERRIDE", "0", "0", "0"),
            _line("AUTOXFADE", "0"),
            _line("ENVLOCKMODE", "0"),
            _line(
                "TEMPO",
                str(project.tempo_bpm),
                str(project.time_sig_num),
                str(project.time_sig_den),
            ),
            _line("PLAYRATE", "1", "0", "0.25", "4"),
            _line("SELECTION", "0", "0"),
            _line("SELECTION2", "0", "0"),
            _line("MASTERAUTOMODE", "0"),
            _line("MASTERTRACKHEIGHT", "0", "0"),
            _line("MASTERTRACKVIEW", "1", "0.6667", "0.5", "0.5", "0", "0", "0"),
        ]
    )
    if project.sample_rate:
        root.children.append(
            _line("SAMPLERATE", str(project.sample_rate), "0", "0"),
        )

    for t_idx, track in enumerate(project.tracks):
        tr = Element("TRACK", ())
        tr.children.extend(
            [
                _line("NAME", track.name or f"Track {t_idx + 1}"),
                _line("PEAKCOL", "16576"),
                _line("BEAT", "-1"),
            ]
        )
        for clip in track.clips:
            length = clip.length_sec
            if length is None:
                length = media_length_seconds(clip.path)
            if length is None or length <= 0:
                length = 4.0

            it = Element("ITEM", ())
            it.children.extend(
                [
                    _line("POSITION", str(clip.position_sec)),
                    _line("SNAPOFFS", "0"),
                    _line("LENGTH", str(length)),
                    _line("FADEIN", "0", "0", "0", "1", "0", "0", "0"),
                    _line("FADEOUT", "0", "0", "0", "1", "0", "0", "0"),
                    _line("MUTE", "0"),
                ]
            )
            sw = Element("SOURCE", _source_tag(clip.path))
            safe_file = sanitize_rpp_file_token(clip.path)
            sw.children.append(_line("FILE", safe_file))
            it.children.append(sw)
            tr.children.append(it)

        root.children.append(tr)

    return root


def write_rpp(project: AcidProject, out_path: Path) -> None:
    """Serialize the project to disk as UTF-8 with Unix newlines."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tree = acid_project_to_rpp(project)
    text = dumps(tree)
    with out_path.open("w", encoding="utf-8", newline="\n") as fp:
        fp.write(text)
