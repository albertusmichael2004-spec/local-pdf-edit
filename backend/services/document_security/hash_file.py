from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Callable

from backend.services.shared.file_hash import HASH_CHUNK_BYTES, sha256_file


PathHashProgress = Callable[[int, int, int, int, str], None]


@dataclass(frozen=True)
class FileHashResult:
    name: str
    bytes: int
    sha256: str
    kind: str = "file"
    files: int = 1


def create_file_hash(path: Path, display_name: str) -> FileHashResult:
    return FileHashResult(
        name=display_name,
        bytes=path.stat().st_size,
        sha256=sha256_file(path),
    )


def create_path_hash(
    path: Path,
    progress: PathHashProgress | None = None,
) -> FileHashResult:
    """Hash one file or a deterministic path/content manifest for a folder."""
    source = path.resolve()
    if not source.exists():
        raise ValueError(f"Path does not exist: {source}")

    if source.is_file():
        total = source.stat().st_size
        completed = 0
        digest = hashlib.sha256()
        with source.open("rb") as stream:
            for chunk in iter(lambda: stream.read(HASH_CHUNK_BYTES), b""):
                digest.update(chunk)
                completed += len(chunk)
                if progress:
                    progress(completed, total, 0, 1, source.name)
        if progress:
            progress(completed, total, 1, 1, source.name)
        return FileHashResult(source.name, completed, digest.hexdigest())

    if not source.is_dir():
        raise ValueError("Only regular files and folders can be hashed.")

    files = sorted(
        (candidate for candidate in source.rglob("*") if candidate.is_file() and not candidate.is_symlink()),
        key=lambda candidate: candidate.relative_to(source).as_posix().casefold(),
    )
    total = sum(candidate.stat().st_size for candidate in files)
    completed = 0
    digest = hashlib.sha256(b"PDFWB-FOLDER-SHA256-V1\0")
    for index, candidate in enumerate(files):
        relative = candidate.relative_to(source).as_posix().encode("utf-8")
        size = candidate.stat().st_size
        digest.update(b"F\0")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(size.to_bytes(8, "big"))
        with candidate.open("rb") as stream:
            for chunk in iter(lambda: stream.read(HASH_CHUNK_BYTES), b""):
                digest.update(chunk)
                completed += len(chunk)
                if progress:
                    progress(completed, total, index, len(files), relative.decode("utf-8"))
        if progress:
            progress(completed, total, index + 1, len(files), relative.decode("utf-8"))

    if progress:
        progress(total, total, len(files), len(files), source.name)
    return FileHashResult(
        name=source.name or str(source),
        bytes=total,
        sha256=digest.hexdigest(),
        kind="folder",
        files=len(files),
    )
