from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import py7zr
import pyzipper

from backend.core.errors import DocumentSecurityError
from backend.core.progress import report_progress
from backend.services.document_security.archive_profiles import choose_archive_profile


MINIMUM_PASSWORD_LENGTH = 8


@dataclass(frozen=True)
class ArchiveBuildResult:
    mode: str
    note: str


def _validated_password(password: str) -> str:
    if len(password) < MINIMUM_PASSWORD_LENGTH:
        raise DocumentSecurityError(
            f"Use a password with at least {MINIMUM_PASSWORD_LENGTH} characters."
        )
    return password


def _archive_name(input_path: Path, stored_name: str | None) -> str:
    """Keep the original display name without ever storing an input path."""
    return Path(stored_name or input_path.name).name


def create_password_protected_zip(
    input_path: Path,
    output_path: Path,
    password: str,
    *,
    stored_name: str | None = None,
) -> ArchiveBuildResult:
    """Wrap one arbitrary file in a WinZip AES-256 encrypted ZIP archive."""
    secret = _validated_password(password).encode("utf-8")
    profile = choose_archive_profile(input_path)
    report_progress("Selecting archive strategy", percent=22, detail=profile.mode)
    compression = pyzipper.ZIP_STORED if profile.mode == "store" else pyzipper.ZIP_DEFLATED
    try:
        with pyzipper.AESZipFile(
            output_path,
            mode="w",
            compression=compression,
            encryption=pyzipper.WZ_AES,
        ) as archive:
            archive.setpassword(secret)
            archive.setencryption(pyzipper.WZ_AES, nbits=256)
            report_progress("Encrypting protected ZIP", percent=30, detail=profile.mode)
            archive.write(input_path, arcname=_archive_name(input_path, stored_name))
        report_progress("Finalizing protected ZIP", percent=94)
        return ArchiveBuildResult(profile.mode, profile.note)
    except DocumentSecurityError:
        raise
    except Exception as exc:
        raise DocumentSecurityError(f"Password-protected ZIP creation failed: {exc}") from exc


def create_7z_archive(
    input_path: Path,
    output_path: Path,
    *,
    stored_name: str | None = None,
) -> ArchiveBuildResult:
    """Compress one arbitrary file into an unencrypted 7z archive."""
    return _write_7z(input_path, output_path, stored_name=stored_name)


def create_aes256_7z(
    input_path: Path,
    output_path: Path,
    password: str,
    *,
    stored_name: str | None = None,
) -> ArchiveBuildResult:
    """Create a password-protected 7z archive with AES-256 and encrypted headers."""
    return _write_7z(
        input_path,
        output_path,
        password=_validated_password(password),
        stored_name=stored_name,
    )


def _write_7z(
    input_path: Path,
    output_path: Path,
    *,
    password: str | None = None,
    stored_name: str | None = None,
) -> ArchiveBuildResult:
    profile = choose_archive_profile(input_path)
    action = "Encrypting AES-256 7z" if password else "Creating 7z archive"
    report_progress("Selecting archive strategy", percent=22, detail=profile.mode)
    try:
        with py7zr.SevenZipFile(
            output_path,
            mode="w",
            password=password,
            header_encryption=password is not None,
            filters=profile.py7zr_filters(),
        ) as archive:
            report_progress(action, percent=30, detail=profile.note)
            archive_name = _archive_name(input_path, stored_name)
            if input_path.is_dir():
                archive.writeall(input_path, arcname=archive_name)
            else:
                archive.write(input_path, arcname=archive_name)
        report_progress("Finalizing encrypted headers" if password else "Finalizing 7z index", percent=94)
        return ArchiveBuildResult(profile.mode, profile.note)
    except Exception as exc:
        raise DocumentSecurityError(f"7z archive creation failed: {exc}") from exc
