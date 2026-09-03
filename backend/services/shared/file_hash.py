from __future__ import annotations

import hashlib
from pathlib import Path
from typing import BinaryIO

from backend.core.progress import report_fraction, report_progress


HASH_CHUNK_BYTES = 16 * 1024 * 1024


def sha256_stream(
    stream: BinaryIO,
    *,
    total: int = 0,
    label: str = "uploaded file",
    require_pdf: bool = False,
    stage: str = "Calculating SHA-256",
    start: float = 20,
    end: float = 92,
) -> tuple[str, int]:
    """Hash a seekable upload spool directly, without a second disk copy."""
    stream.seek(0)
    if not total:
        stream.seek(0, 2)
        total = stream.tell()
        stream.seek(0)
    digest = hashlib.sha256()
    completed = 0
    first_chunk = True
    report_progress(stage, percent=start, detail=label)
    for chunk in iter(lambda: stream.read(HASH_CHUNK_BYTES), b""):
        if first_chunk and require_pdf and not chunk.startswith(b"%PDF-"):
            raise ValueError("The uploaded file does not look like a valid PDF.")
        first_chunk = False
        digest.update(chunk)
        completed += len(chunk)
        report_fraction(stage, completed, total, start, end)
    if not completed:
        raise ValueError("The uploaded file is empty.")
    return digest.hexdigest(), completed


def sha256_file(path: Path) -> str:
    total = path.stat().st_size
    with path.open("rb") as stream:
        digest, _ = sha256_stream(stream, total=total, label=path.name)
    return digest
