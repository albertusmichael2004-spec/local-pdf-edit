from __future__ import annotations

import bz2
from dataclasses import dataclass
import gzip
import lzma
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import tarfile
import zipfile

import py7zr
import pyzipper

from backend.core.errors import DocumentSecurityError
from backend.core.progress import report_fraction, report_progress
from backend.core.subprocesses import run_hidden


MAX_ARCHIVE_ENTRIES = 10_000
COPY_CHUNK_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True)
class ArchiveExtractionResult:
    destination: Path
    file_count: int
    total_bytes: int
    archive_type: str


def extract_archive_any(
    input_path: Path,
    destination: Path,
    password: str = "",
) -> ArchiveExtractionResult:
    """Safely extract common archive/compression formats without a size cap."""
    source = Path(input_path).resolve()
    if not source.is_file():
        raise DocumentSecurityError("Choose an existing compressed file.")
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    kind = _archive_kind(source)
    report_progress("Inspecting compressed file", percent=12, detail=source.name)
    try:
        if kind == "zip":
            files = _extract_zip(source, destination, password)
        elif kind == "7z":
            files = _extract_7z(source, destination, password)
        elif kind == "tar":
            files = _extract_tar(source, destination)
        elif kind in {"gz", "bz2", "xz"}:
            files = [_extract_single_stream(source, destination, kind)]
        else:
            files = _extract_with_windows_tar(source, destination)
    except DocumentSecurityError:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(destination, ignore_errors=True)
        raise DocumentSecurityError(
            "Extraction failed. The file may be damaged, encrypted with an unsupported method, or use an unsupported format."
        ) from exc
    if not files:
        shutil.rmtree(destination, ignore_errors=True)
        raise DocumentSecurityError("The compressed file does not contain any regular files.")
    total = sum(path.stat().st_size for path in files if path.is_file())
    report_progress("Extraction complete", percent=100, detail=f"{len(files)} file(s)")
    return ArchiveExtractionResult(destination, len(files), total, kind)


def _archive_kind(path: Path) -> str:
    lower = path.name.lower()
    if zipfile.is_zipfile(path):
        return "zip"
    if py7zr.is_7zfile(path):
        return "7z"
    if tarfile.is_tarfile(path):
        return "tar"
    if lower.endswith(".gz"):
        return "gz"
    if lower.endswith(".bz2"):
        return "bz2"
    if lower.endswith(".xz"):
        return "xz"
    return "system-archive"


def _safe_target(root: Path, member_name: str) -> Path:
    normalized = member_name.replace("\\", "/")
    member = PurePosixPath(normalized)
    if (
        not normalized
        or "\x00" in normalized
        or member.is_absolute()
        or any(part in {"", ".", ".."} or ":" in part for part in member.parts)
    ):
        raise DocumentSecurityError("The archive contains an unsafe file path.")
    target = root.joinpath(*member.parts).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise DocumentSecurityError("The archive contains an unsafe file path.") from exc
    return target


def _validate_count(count: int) -> None:
    if count > MAX_ARCHIVE_ENTRIES:
        raise DocumentSecurityError(
            f"The archive contains more than {MAX_ARCHIVE_ENTRIES:,} entries."
        )


def _extract_zip(source: Path, destination: Path, password: str) -> list[Path]:
    files: list[Path] = []
    targets: set[Path] = set()
    written = 0
    try:
        with pyzipper.AESZipFile(source, "r") as archive:
            if password:
                archive.setpassword(password.encode("utf-8"))
            members = archive.infolist()
            _validate_count(len(members))
            declared = sum(item.file_size for item in members if not item.is_dir())
            for item in members:
                target = _safe_target(destination, item.filename)
                if target in targets:
                    raise DocumentSecurityError("The archive contains duplicate file paths.")
                targets.add(target)
                file_type = stat.S_IFMT(item.external_attr >> 16)
                if file_type not in {0, stat.S_IFREG, stat.S_IFDIR}:
                    raise DocumentSecurityError("Archive links and special files are not supported.")
                if item.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(item, "r") as reader, target.open("wb") as writer:
                    while chunk := reader.read(COPY_CHUNK_BYTES):
                        writer.write(chunk)
                        written += len(chunk)
                        report_fraction("Extracting ZIP", written, declared, 20, 94)
                files.append(target)
    except DocumentSecurityError:
        raise
    except (RuntimeError, zipfile.BadZipFile, NotImplementedError) as exc:
        raise DocumentSecurityError(
            "Could not extract the ZIP. Check its password and integrity."
        ) from exc
    return files


def _extract_7z(source: Path, destination: Path, password: str) -> list[Path]:
    try:
        with py7zr.SevenZipFile(source, "r", password=password or None) as archive:
            members = archive.list()
            _validate_count(len(members))
            files: list[Path] = []
            targets: set[Path] = set()
            for item in members:
                target = _safe_target(destination, item.filename)
                if target in targets:
                    raise DocumentSecurityError("The archive contains duplicate file paths.")
                targets.add(target)
                if item.is_symlink or (not item.is_file and not item.is_directory):
                    raise DocumentSecurityError("Archive links and special files are not supported.")
                if item.is_file:
                    files.append(target)
            archive.extractall(path=destination)
            return files
    except DocumentSecurityError:
        raise
    except Exception as exc:
        raise DocumentSecurityError(
            "Could not extract the 7z. Check its password and integrity."
        ) from exc


def _extract_tar(source: Path, destination: Path) -> list[Path]:
    files: list[Path] = []
    with tarfile.open(source, "r:*") as archive:
        members = archive.getmembers()
        _validate_count(len(members))
        declared = sum(item.size for item in members if item.isfile())
        written = 0
        targets: set[Path] = set()
        for item in members:
            target = _safe_target(destination, item.name)
            if target in targets:
                raise DocumentSecurityError("The archive contains duplicate file paths.")
            targets.add(target)
            if item.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not item.isfile():
                raise DocumentSecurityError("Archive links and special files are not supported.")
            reader = archive.extractfile(item)
            if reader is None:
                raise DocumentSecurityError(f"Could not read archive entry: {item.name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with reader, target.open("wb") as writer:
                while chunk := reader.read(COPY_CHUNK_BYTES):
                    writer.write(chunk)
                    written += len(chunk)
                    report_fraction("Extracting TAR", written, declared, 20, 94)
            files.append(target)
    return files


def _extract_single_stream(source: Path, destination: Path, kind: str) -> Path:
    openers = {"gz": gzip.open, "bz2": bz2.open, "xz": lzma.open}
    suffix_length = len(f".{kind}")
    output_name = source.name[:-suffix_length] or f"{source.stem}_extracted"
    target = _safe_target(destination, output_name)
    with openers[kind](source, "rb") as reader, target.open("wb") as writer:
        shutil.copyfileobj(reader, writer, COPY_CHUNK_BYTES)
    return target


def _extract_with_windows_tar(source: Path, destination: Path) -> list[Path]:
    executable = shutil.which("tar")
    if not executable:
        raise DocumentSecurityError(
            "This archive format is not supported by the bundled extractors or Windows tar."
        )
    listing = run_hidden(
        [executable, "-tf", str(source)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if listing.returncode != 0:
        raise DocumentSecurityError("This compressed-file format is not supported on this computer.")
    names = [name.strip() for name in listing.stdout.splitlines() if name.strip()]
    _validate_count(len(names))
    targets = [_safe_target(destination, name) for name in names]
    if len(set(targets)) != len(targets):
        raise DocumentSecurityError("The archive contains duplicate file paths.")
    verbose = run_hidden(
        [executable, "-tvf", str(source)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    verbose_lines = [line for line in verbose.stdout.splitlines() if line.strip()]
    if verbose.returncode != 0 or len(verbose_lines) != len(names):
        raise DocumentSecurityError("Could not safely inspect this archive format.")
    if any(line.lstrip()[:1] not in {"-", "d"} for line in verbose_lines):
        raise DocumentSecurityError("Archive links and special files are not supported.")
    completed = run_hidden(
        [executable, "-xf", str(source), "-C", str(destination)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise DocumentSecurityError(
            f"Windows could not extract this archive: {(completed.stderr or '').strip()[-500:]}"
        )
    files: list[Path] = []
    for path in destination.rglob("*"):
        if path.is_symlink() or os.path.islink(path):
            raise DocumentSecurityError("Archive links and special files are not supported.")
        if path.is_file():
            files.append(path)
    return files
