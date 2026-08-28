"""Tests for path validation and ZIP safety limits."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

import acid2reaper.containers as containers
from acid2reaper.containers import extract_acd_zip
from acid2reaper.exceptions import SecurityError, ZipBombError
from acid2reaper.security import MAX_ZIP_MEMBERS, validate_user_path


def test_too_many_zip_members_rejected(tmp_path: Path) -> None:
    """Archives with more than MAX_ZIP_MEMBERS entries are rejected (zip bomb / abuse)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for i in range(MAX_ZIP_MEMBERS + 1):
            zf.writestr(f"member{i}.txt", b"x")
    zip_path = tmp_path / "many_members.zip"
    zip_path.write_bytes(buf.getvalue())

    with pytest.raises(ZipBombError):
        extract_acd_zip(zip_path)


def test_zip_slip_member_rejected_without_writing_outside(tmp_path: Path) -> None:
    """An archive member cannot escape the dedicated extraction directory."""
    zip_path = tmp_path / "traversal.acd-zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("project.acd", b"project")
        zf.writestr("../escaped.txt", b"unsafe")

    with pytest.raises(SecurityError, match="Unsafe path"):
        extract_acd_zip(zip_path)

    assert not (tmp_path / "escaped.txt").exists()


def test_zip_uncompressed_size_cap_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Declared uncompressed content over the configured cap is rejected cheaply."""
    monkeypatch.setattr(containers, "MAX_ZIP_UNCOMPRESSED_BYTES", 8)
    zip_path = tmp_path / "oversize.acd-zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("project.acd", b"123456789")

    with pytest.raises(ZipBombError, match="uncompressed size"):
        extract_acd_zip(zip_path)


def test_validate_rejects_null_in_path() -> None:
    """NUL bytes in paths are a common injection vector; refuse early."""
    with pytest.raises(SecurityError):
        validate_user_path(Path("foo\x00bar"), must_exist=False, must_be_file=False)
