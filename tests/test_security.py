"""Tests for path validation and ZIP safety limits."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

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


def test_validate_rejects_null_in_path() -> None:
    """NUL bytes in paths are a common injection vector; refuse early."""
    with pytest.raises(SecurityError):
        validate_user_path(Path("foo\x00bar"), must_exist=False, must_be_file=False)
