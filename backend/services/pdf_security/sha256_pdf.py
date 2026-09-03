from __future__ import annotations

from pathlib import Path

from backend.services.shared.file_hash import sha256_file as _sha256_file


def sha256_file(path: Path) -> str:
    """Compatibility wrapper for the PDF-security service API."""
    return _sha256_file(path)
