from __future__ import annotations

import re
from pathlib import Path
from typing import BinaryIO

from fastapi import UploadFile


_PDF_HEADER = b"%PDF-"


def safe_filename(name: str | None, fallback: str = "file.pdf") -> str:
    """Return a conservative filesystem-safe file name."""
    raw = Path(name or fallback).name
    raw = re.sub(r"[^A-Za-z0-9._()\- ]+", "_", raw).strip(" .")
    return raw or fallback


async def save_upload(
    upload: UploadFile,
    destination: Path,
    max_bytes: int,
    require_pdf: bool = True,
) -> int:
    """Stream an uploaded file to disk while enforcing a size limit.

    Returns the number of bytes written.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    first_chunk = True

    with destination.open("wb") as output:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            if first_chunk and require_pdf and not chunk.startswith(_PDF_HEADER):
                raise ValueError("The uploaded file does not look like a valid PDF.")
            first_chunk = False
            written += len(chunk)
            if written > max_bytes:
                raise ValueError(
                    f"File is larger than the configured {max_bytes / 1024 / 1024:.0f} MB limit."
                )
            output.write(chunk)

    await upload.close()
    if written == 0:
        raise ValueError("The uploaded file is empty.")
    return written


def write_bytes(stream: BinaryIO, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as output:
        while chunk := stream.read(1024 * 1024):
            output.write(chunk)
