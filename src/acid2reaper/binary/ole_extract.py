from __future__ import annotations

import io
from typing import List, Optional

try:
    import olefile  # type: ignore[import-untyped]
except ImportError:
    olefile = None


def ole_concat_stream_bytes(data: bytes) -> Optional[bytes]:
    """
    If `data` is an OLE compound document, concatenate readable stream payloads.
    Requires optional dependency `olefile`.
    """
    if olefile is None or len(data) < 512:
        return None
    if data[:8] != b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return None
    try:
        ole = olefile.OleFileIO(io.BytesIO(data))  # type: ignore[misc]
    except Exception:
        return None
    parts: List[bytes] = []
    try:
        for path in ole.listdir():
            try:
                parts.append(ole.openstream(path).read())
            except Exception:
                continue
    except Exception:
        return None
    finally:
        try:
            ole.close()
        except Exception:
            pass
    return b"\n".join(parts) if parts else None
