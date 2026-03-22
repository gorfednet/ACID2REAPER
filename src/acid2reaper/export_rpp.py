"""
Build a REAPER `.rpp` document tree and write UTF-8 text (ACID2Reaper output).

Emits a **master** bus, then each **track** with routing (groups, channel mode),
**FXCHAIN** blocks, **AUXRECV** sends, and **ITEM** regions. File paths are passed
through :func:`sanitize_rpp_file_token` so control characters cannot break parsing.
"""

from __future__ import annotations

from pathlib import Path

from rpp import dumps
from rpp.element import Element

from .media_duration import media_length_seconds
from .model import AcidClip, AcidProject, AcidTrack, FxSlot, MasterBus
from .rpp_format import format_rpp_float
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


def _item_playrate_tokens(clip: AcidClip) -> tuple[str, ...]:
    """REAPER `PLAYRATE` line: rate (negative = reverse) + seven trailing fields."""
    r = float(clip.playrate)
    if clip.reverse:
        r = -abs(r)
    else:
        r = abs(r)
    if r == 0.0:
        r = 1.0
    return (format_rpp_float(r), "0", "0", "0", "0", "0", "0", "0")


def _fxchain_element(slots: list[FxSlot]) -> Element:
    """Build an ``FXCHAIN`` with optional ``FXID`` children (empty shell if none)."""
    ch = Element("FXCHAIN", ())
    ch.children.extend(
        [
            _line("SHOW", "0"),
            _line("LASTSEL", "0"),
            _line("BYPASS", "0", "0", "0"),
            _line("FLOATPOS", "0", "0", "0", "0"),
        ]
    )
    for slot in slots:
        if not slot.fxid_reaper:
            continue
        fx = Element("FXID", (slot.fxid_reaper,))
        fx.children.append(_line("WET", format_rpp_float(slot.wet)))
        if slot.bypass:
            fx.children.append(_line("BYPASS", "1"))
        ch.children.append(fx)
    return ch


def _master_track_element(master: MasterBus) -> Element:
    """Build the master ``TRACK`` (empty NAME, first in project)."""
    tr = Element("TRACK", ())
    mute = 1 if master.mute else 0
    tr.children.extend(
        [
            _line("NAME", ""),
            _line("PEAKCOL", "16576"),
            _line("BEAT", "-1"),
            _line(
                "VOLPAN",
                format_rpp_float(master.volume_linear),
                format_rpp_float(master.pan),
                "1",
                "-1",
            ),
            _line("MUTESOLO", str(mute), "0", "0"),
            _line("IPLUGINSTATE", "0", "0", "0", "0", "0", "0"),
        ]
    )
    tr.children.append(_fxchain_element(master.fx))
    return tr


def _regular_track_element(track: AcidTrack, track_index: int) -> Element:
    """Build one non-master AUDIO track (``track_index`` is 1-based for display only)."""
    tr = Element("TRACK", ())
    mute = 1 if track.mute else 0
    solo = 1 if track.solo else 0
    tr.children.extend(
        [
            _line("NAME", track.name or f"Track {track_index}"),
            _line("PEAKCOL", "16576"),
            _line("BEAT", "-1"),
            _line("TRACKHEIGHT", "0", "0", "0"),
            _line("CHANMODE", str(track.chan_mode)),
            _line("TRACKTYPE", str(track.track_type)),
            _line("FOLDERDEPTH", str(track.folder_depth)),
            _line(
                "VOLPAN",
                format_rpp_float(track.volume_linear),
                format_rpp_float(track.pan),
                "1",
                "-1",
            ),
            _line("MUTESOLO", str(mute), str(solo), "0"),
            _line("TRACKGROUP", str(track.track_group_id)),
            _line("IPLUGINSTATE", "0", "0", "0", "0", "0", "0"),
        ]
    )
    tr.children.append(_fxchain_element(track.fx))

    for send in track.sends:
        # REAPER AUXRECV: destination track index, level, pan, … (nine trailing fields).
        tr.children.append(
            _line(
                "AUXRECV",
                str(send.dest_track_index),
                format_rpp_float(send.volume_linear),
                format_rpp_float(send.pan),
                "0",
                "0",
                "0",
                "0",
                "0",
                "0",
            )
        )

    for clip in track.clips:
        length = clip.length_sec
        if length is None:
            length = media_length_seconds(clip.path)
        if length is None or length <= 0:
            length = 4.0

        it = Element("ITEM", ())
        it.children.append(_line("POSITION", format_rpp_float(clip.position_sec)))
        snap = clip.source_trim_start_sec if clip.source_trim_start_sec else 0.0
        it.children.append(_line("SNAPOFFS", format_rpp_float(snap)))
        it.children.append(_line("LENGTH", format_rpp_float(length)))

        vol = max(0.0, float(clip.volume_linear))
        pan = max(-1.0, min(1.0, float(clip.pan)))
        it.children.append(
            _line("VOLPAN", format_rpp_float(vol), format_rpp_float(pan), "1", "-1")
        )

        ps = float(clip.pitch_semitones)
        if abs(ps) > 1e-9:
            it.children.append(
                _line("PITCHSHIFT", format_rpp_float(ps), "0", "0", "0", "0", "0")
            )

        if abs(float(clip.playrate) - 1.0) > 1e-9 or clip.reverse:
            it.children.append(_line("PLAYRATE", *_item_playrate_tokens(clip)))

        it.children.extend(
            [
                _line("FADEIN", "0", "0", "0", "1", "0", "0", "0"),
                _line("FADEOUT", "0", "0", "0", "1", "0", "0", "0"),
                _line("MUTE", "1" if clip.mute else "0"),
            ]
        )
        sw = Element("SOURCE", _source_tag(clip.path))
        safe_file = sanitize_rpp_file_token(clip.path)
        sw.children.append(_line("FILE", safe_file))
        it.children.append(sw)
        tr.children.append(it)

    return tr


def acid_project_to_rpp(project: AcidProject) -> Element:
    """
    Turn our normalized :class:`AcidProject` into the root `REAPER_PROJECT` element.

    Track order is **master first**, then each :class:`AcidTrack` in order.
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

    root.children.append(_master_track_element(project.master))

    for i, track in enumerate(project.tracks, start=1):
        root.children.append(_regular_track_element(track, i))

    return root


def write_rpp(project: AcidProject, out_path: Path) -> None:
    """Serialize the project to disk as UTF-8 with Unix newlines."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tree = acid_project_to_rpp(project)
    text = dumps(tree)
    with out_path.open("w", encoding="utf-8", newline="\n") as fp:
        fp.write(text)
