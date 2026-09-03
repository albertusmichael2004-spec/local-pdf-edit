from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import py7zr


FAST_THRESHOLD_BYTES = 512 * 1024 * 1024
PRECOMPRESSED_SUFFIXES = frozenset({
    ".7z", ".aac", ".avi", ".bz2", ".docx", ".epub", ".flac", ".gif",
    ".gz", ".heic", ".jpeg", ".jpg", ".m4a", ".mkv", ".mov", ".mp3",
    ".mp4", ".ogg", ".opus", ".pdf", ".png", ".pptx", ".rar", ".webm",
    ".webp", ".xlsx", ".xz", ".zip", ".zst",
})
PRECOMPRESSED_HEADERS = (
    b"PK\x03\x04", b"7z\xbc\xaf\x27\x1c", b"Rar!", b"\x1f\x8b", b"\xfd7zXZ",
    b"\x89PNG", b"\xff\xd8\xff",
)


@dataclass(frozen=True)
class ArchiveProfile:
    mode: str
    filter_id: int | None
    note: str

    def py7zr_filters(self) -> list[dict[str, int]] | None:
        return [{"id": self.filter_id}] if self.filter_id is not None else None


def choose_archive_profile(path: Path) -> ArchiveProfile:
    if path.is_dir():
        total_bytes = sum(
            candidate.stat().st_size
            for candidate in path.rglob("*")
            if candidate.is_file() and not candidate.is_symlink()
        )
        if total_bytes >= FAST_THRESHOLD_BYTES:
            return ArchiveProfile(
                "fast-deflate",
                py7zr.FILTER_DEFLATE,
                "Fast mode: large folder used fast Deflate compression.",
            )
        return ArchiveProfile(
            "standard-lzma2",
            None,
            "The complete folder tree was compressed with standard LZMA2.",
        )
    if _already_compressed(path):
        return ArchiveProfile(
            "store",
            py7zr.FILTER_COPY,
            "Fast mode: existing compressed data was stored without recompression.",
        )
    if path.stat().st_size >= FAST_THRESHOLD_BYTES:
        return ArchiveProfile(
            "fast-deflate",
            py7zr.FILTER_DEFLATE,
            "Fast mode: large input used fast Deflate compression.",
        )
    return ArchiveProfile(
        "standard-lzma2",
        None,
        "Standard LZMA2 compression was used.",
    )


def _already_compressed(path: Path) -> bool:
    if path.suffix.lower() in PRECOMPRESSED_SUFFIXES:
        return True
    with path.open("rb") as source:
        header = source.read(8)
    return any(header.startswith(signature) for signature in PRECOMPRESSED_HEADERS)
