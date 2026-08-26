from __future__ import annotations

from pathlib import Path

from backend.services.pdf_security.sha256_pdf import sha256_file


def compare_sha256(left_path: Path, right_path: Path) -> tuple[str, str, bool]:
    """Return both SHA-256 digests and whether the files are byte-identical."""
    left_hash = sha256_file(left_path)
    right_hash = sha256_file(right_path)
    return left_hash, right_hash, left_hash == right_hash
