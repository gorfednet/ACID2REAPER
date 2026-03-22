"""Tests for UTF-16LE string scanning helpers used across the parser."""

from acid2reaper.string_scan import utf16le_ascii_runs, utf16le_runs_filtered


def _utf16le_ascii(s: str) -> bytes:
    return "".join(f"{c}\0" for c in s).encode("latin-1")


def test_utf16le_ascii_runs_finds_embedded_path() -> None:
    blob = b"\xff\xff" + _utf16le_ascii("C:\\Loops\\clip.wav") + b"\x00\x00"
    hits = utf16le_ascii_runs(blob)
    texts = [t for _o, t in hits]
    assert any("clip.wav" in t for t in texts)


def test_utf16le_runs_filtered_wav_only() -> None:
    # UTF-16 NUL terminator so the scanner does not merge with a following run.
    blob = _utf16le_ascii("C:\\a\\x.wav") + b"\x00\x00"

    def is_wav(s: str) -> bool:
        return s.lower().endswith(".wav")

    filtered = utf16le_runs_filtered(blob, is_wav)
    assert len(filtered) == 1
    assert filtered[0][1].endswith("x.wav")
