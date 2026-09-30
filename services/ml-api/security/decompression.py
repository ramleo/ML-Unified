"""Zip-bomb / decompression guard for archive-type uploads.

A `.docx`/`.xlsx` is a ZIP, and a small crafted archive can inflate to gigabytes
on extraction and OOM the Space before any content code runs — something the
byte-size cap in `security/body_size.py` cannot see (it only measures the
*compressed* upload). This inspects the ZIP central directory (declared sizes and
entry count — no extraction, so it's cheap) and rejects an archive whose total
uncompressed size, compression ratio, or entry count is implausible.

No-op on non-ZIP bytes (e.g. a PDF or image), so it is safe to call on any
upload. Only the classic bomb shape (huge declared sizes / tiny compressed / many
entries) is rejected; ordinary Office documents are far below these limits.
"""
from __future__ import annotations

import io
import zipfile

from fastapi import HTTPException

from security.events import log_security_event

MAX_TOTAL_UNCOMPRESSED = 150 * 1024 * 1024  # 150 MB expanded across all entries
MAX_RATIO = 200                             # uncompressed : compressed
MAX_ENTRIES = 10_000


def zip_bomb_check(data: bytes, path: str = "", client_ip: str = "") -> None:
    """Reject (HTTP 413) an archive that looks like a decompression bomb. No-op
    if `data` is not a ZIP. Never raises for a non-bomb archive."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            infos = z.infolist()
    except (zipfile.BadZipFile, OSError):
        return  # not a ZIP — nothing to guard here
    if not infos:
        return
    total_unc = sum(i.file_size for i in infos)
    total_cmp = sum(i.compress_size for i in infos) or 1
    ratio = total_unc / total_cmp

    reason = None
    if len(infos) > MAX_ENTRIES:
        reason = f"entries={len(infos)}"
    elif total_unc > MAX_TOTAL_UNCOMPRESSED:
        reason = f"uncompressed={total_unc}"
    elif ratio > MAX_RATIO:
        reason = f"ratio={ratio:.0f}"

    if reason:
        log_security_event("zip_bomb_blocked", path, client_ip, detail=reason)
        raise HTTPException(
            status_code=413,
            detail="Archive rejected: its decompressed size or ratio exceeds safe limits.",
        )
