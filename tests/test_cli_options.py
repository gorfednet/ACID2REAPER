"""CLI surface: time-signature options, note reporting, exit codes."""

from __future__ import annotations

from pathlib import Path

import pytest

from acid2reaper.cli import _parse_time_sig, convert, main
from acid2reaper.exceptions import Acid2ReaperError

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ACD = FIXTURES / "DrumRollUpDemo.acd"


@pytest.mark.parametrize(
    "text, expected",
    [("4/4", (4, 4)), ("6/8", (6, 8)), (" 7 / 8 ", (7, 8)), ("12/16", (12, 16))],
)
def test_time_sig_parsing(text: str, expected) -> None:
    assert _parse_time_sig(text) == expected


@pytest.mark.parametrize("text", ["", "4", "4-4", "x/4", "0/4", "33/4", "4/5", "4/0", "4/64"])
def test_time_sig_rejects_bad_input(text: str) -> None:
    with pytest.raises(Acid2ReaperError):
        _parse_time_sig(text)


def test_time_sig_override_reaches_the_tempo_line(tmp_path: Path) -> None:
    out = tmp_path / "override.rpp"
    convert(ACD, out, time_sig_override=(7, 8))
    assert "TEMPO 120 7 8" in out.read_text(encoding="utf-8")


def test_notes_callback_receives_the_diagnostics(tmp_path: Path) -> None:
    captured: list[str] = []
    convert(ACD, tmp_path / "notes.rpp", on_notes=captured.extend)
    assert captured
    assert any("Project tempo" in note for note in captured)


def test_main_reports_notes_only_when_verbose(tmp_path: Path, capsys) -> None:
    assert main([str(ACD), str(tmp_path / "quiet.rpp"), "-q"]) == 0
    assert "Project tempo" not in capsys.readouterr().err

    assert main([str(ACD), str(tmp_path / "loud.rpp"), "-q", "-v"]) == 0
    assert "Project tempo" in capsys.readouterr().err


def test_main_rejects_a_bad_time_signature(tmp_path: Path, capsys) -> None:
    assert main([str(ACD), str(tmp_path / "bad.rpp"), "--time-sig", "4/5"]) == 1
    assert "--time-sig denominator" in capsys.readouterr().err


def test_main_without_input_is_exit_code_2(capsys) -> None:
    assert main([]) == 2
    assert "required: input" in capsys.readouterr().err
