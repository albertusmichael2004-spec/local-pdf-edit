from __future__ import annotations

from dataclasses import dataclass
import mimetypes
from pathlib import Path, PurePosixPath
import shutil
import stat
import zipfile

import py7zr
import pyzipper

from backend.core.errors import DocumentSecurityError
from backend.core.progress import report_fraction, report_progress


MAX_ARCHIVE_ENTRIES = 1_000
COPY_CHUNK_BYTES = 1024 * 1024


@dataclass(frozen=True)
class DecryptionResult:
    path: Path
    download_name: str
    media_type: str
    file_count: int


def decrypt_archive(
    input_path: Path,
    output_dir: Path,
    password: str,
    *,
    archive_stem: str = "document",
    max_output_bytes: int | None = None,
) -> DecryptionResult:
    """Decrypt a ZIP/7z safely and prepare either one file or a plain ZIP."""
    if not password:
        raise DocumentSecurityError("Enter the archive password.")
    if max_output_bytes is not None and max_output_bytes <= 0:
        raise ValueError("Maximum output size must be greater than zero.")

    extracted_dir = output_dir / "decrypted_contents"
    extracted_dir.mkdir(parents=True, exist_ok=True)
    try:
        report_progress("Inspecting encrypted archive", percent=22, detail=input_path.name)
        if zipfile.is_zipfile(input_path):
            files = _extract_zip(input_path, extracted_dir, password, max_output_bytes)
        elif py7zr.is_7zfile(input_path):
            files = _extract_7z(input_path, extracted_dir, password, max_output_bytes)
        else:
            raise DocumentSecurityError(
                "Unsupported encrypted file. Choose a password-protected ZIP or 7z archive."
            )
        report_progress("Preparing decrypted download", percent=92, detail=f"{len(files)} file(s)")
        return _prepare_download(files, extracted_dir, output_dir, archive_stem)
    except DocumentSecurityError:
        raise
    except Exception as exc:
        raise DocumentSecurityError(
            "Decryption failed. Check the password and make sure the archive is not damaged."
        ) from exc


def _extract_zip(
    input_path: Path,
    destination: Path,
    password: str,
    max_output_bytes: int,
) -> list[Path]:
    extracted: list[Path] = []
    targets: set[Path] = set()
    written = 0
    try:
        with pyzipper.AESZipFile(input_path, mode="r") as archive:
            archive.setpassword(password.encode("utf-8"))
            members = archive.infolist()
            _validate_entry_count(len(members))
            declared_size = sum(info.file_size for info in members if not info.is_dir())
            _validate_total_size(declared_size, max_output_bytes)

            for info in members:
                target = _safe_member_path(destination, info.filename)
                if target in targets:
                    raise DocumentSecurityError("The archive contains duplicate file paths.")
                targets.add(target)
                if _zip_member_is_unsafe_type(info):
                    raise DocumentSecurityError(
                        "Archives containing links or special files are not supported."
                    )
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info, mode="r") as source, target.open("wb") as output:
                    while chunk := source.read(COPY_CHUNK_BYTES):
                        written += len(chunk)
                        _validate_total_size(written, max_output_bytes)
                        output.write(chunk)
                        report_fraction("Decrypting ZIP contents", written, declared_size, 28, 88)
                extracted.append(target)
    except DocumentSecurityError:
        raise
    except (RuntimeError, zipfile.BadZipFile, NotImplementedError) as exc:
        raise DocumentSecurityError(
            "Could not decrypt the ZIP. The password may be incorrect or the archive is damaged."
        ) from exc
    return extracted


def _extract_7z(
    input_path: Path,
    destination: Path,
    password: str,
    max_output_bytes: int,
) -> list[Path]:
    try:
        options = {"mode": "r", "password": password}
        if max_output_bytes is not None:
            options["max_extract_size"] = max_output_bytes
        with py7zr.SevenZipFile(input_path, **options) as archive:
            members = archive.list()
            _validate_entry_count(len(members))
            regular_members = []
            targets: set[Path] = set()
            for info in members:
                target = _safe_member_path(destination, info.filename)
                if target in targets:
                    raise DocumentSecurityError("The archive contains duplicate file paths.")
                targets.add(target)
                if info.is_symlink or (not info.is_file and not info.is_directory):
                    raise DocumentSecurityError(
                        "Archives containing links or special files are not supported."
                    )
                if info.is_file:
                    regular_members.append(info)
            _validate_total_size(
                sum(info.uncompressed for info in regular_members),
                max_output_bytes,
            )
            report_progress("Decrypting 7z contents", percent=35, detail=f"{len(regular_members)} file(s)")
            archive.extractall(path=destination)
            return [_safe_member_path(destination, info.filename) for info in regular_members]
    except DocumentSecurityError:
        raise
    except Exception as exc:
        raise DocumentSecurityError(
            "Could not decrypt the 7z. The password may be incorrect or the archive is damaged."
        ) from exc


def _prepare_download(
    files: list[Path],
    extracted_dir: Path,
    output_dir: Path,
    archive_stem: str,
) -> DecryptionResult:
    if not files:
        raise DocumentSecurityError("The archive does not contain any files.")
    if len(files) == 1:
        source = files[0]
        download_name = source.name
        download_dir = output_dir / "decrypted_download"
        download_dir.mkdir(parents=True, exist_ok=True)
        output = download_dir / download_name
        shutil.copyfile(source, output)
        media_type = mimetypes.guess_type(download_name)[0] or "application/octet-stream"
        return DecryptionResult(output, download_name, media_type, 1)

    output = output_dir / f"{archive_stem}_decrypted.zip"
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, arcname=path.relative_to(extracted_dir).as_posix())
    return DecryptionResult(output, output.name, "application/zip", len(files))


def _safe_member_path(root: Path, member_name: str) -> Path:
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


def _zip_member_is_unsafe_type(info: zipfile.ZipInfo) -> bool:
    file_type = stat.S_IFMT(info.external_attr >> 16)
    return file_type not in {0, stat.S_IFREG, stat.S_IFDIR}


def _validate_entry_count(count: int) -> None:
    if count > MAX_ARCHIVE_ENTRIES:
        raise DocumentSecurityError(
            f"The archive contains more than {MAX_ARCHIVE_ENTRIES:,} entries."
        )


def _validate_total_size(size: int, maximum: int | None) -> None:
    if maximum is not None and size > maximum:
        raise DocumentSecurityError(
            f"Decrypted content exceeds the configured {maximum / 1024 / 1024:.0f} MB limit."
        )
