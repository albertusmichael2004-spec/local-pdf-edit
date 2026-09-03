from __future__ import annotations

import re
from pathlib import Path
from typing import BinaryIO

from fastapi import UploadFile

from backend.core.progress import report_fraction, report_progress


_PDF_HEADER = b"%PDF-"
UPLOAD_CHUNK_BYTES = 8 * 1024 * 1024


def safe_filename(name: str | None, fallback: str = "file.pdf") -> str:
    """Return a conservative filesystem-safe file name."""
    raw = Path(name or fallback).name
    raw = re.sub(r"[^A-Za-z0-9._()\- ]+", "_", raw).strip(" .")
    return raw or fallback


async def save_upload(
    upload: UploadFile,
    destination: Path,
    require_pdf: bool = True,
) -> int:
    """Stream an uploaded file to disk without an application size cap.

    Returns the number of bytes written.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    first_chunk = True
    total = int(getattr(upload, "size", 0) or 0)
    label = safe_filename(upload.filename, destination.name)
    report_progress("Staging upload on local disk", percent=3, detail=label)

    with destination.open("wb") as output:
        while True:
            chunk = await upload.read(UPLOAD_CHUNK_BYTES)
            if not chunk:
                break
            if first_chunk and require_pdf and not chunk.startswith(_PDF_HEADER):
                raise ValueError("The uploaded file does not look like a valid PDF.")
            first_chunk = False
            written += len(chunk)
            output.write(chunk)
            if total:
                report_fraction("Staging upload on local disk", written, total, 3, 18)
            else:
                report_progress(
                    "Staging upload on local disk",
                    detail=f"{written / (1024 * 1024):,.1f} MB copied",
                )

    await upload.close()
    if written == 0:
        raise ValueError("The uploaded file is empty.")
    return written


def write_bytes(stream: BinaryIO, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as output:
        while chunk := stream.read(1024 * 1024):
            output.write(chunk)
