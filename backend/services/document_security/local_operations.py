from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

import py7zr
from send2trash import send2trash

from backend.core.errors import DocumentSecurityError
from backend.services.document_security.archive_security import create_aes256_7z


@dataclass(frozen=True)
class LocalSecurityResult:
    output_path: Path
    original_trashed: bool
    note: str


def unique_path(parent: Path, name: str) -> Path:
    candidate = parent / name
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    for index in range(2, 10_000):
        candidate = parent / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate
    raise DocumentSecurityError("Could not allocate a unique output name.")


def secure_local_file(
    source_path: Path,
    password: str,
    delete_original: bool = False,
    reduce_size: bool = False,
) -> LocalSecurityResult:
    source = Path(source_path).resolve()
    if not source.is_file() and not source.is_dir():
        raise DocumentSecurityError("Choose an existing source file or folder.")
    output = unique_path(source.parent, f"{source.stem}_secured.7z")
    try:
        with TemporaryDirectory(prefix=".pdf-workbench-security-", dir=source.parent) as temp_dir:
            archive_input = source
            optimization_note = ""
            if reduce_size and source.is_file():
                from backend.services.document_security.content_optimization import prepare_balanced_content

                optimized = prepare_balanced_content(source, Path(temp_dir), source.name)
                archive_input = optimized.path
                optimization_note = optimized.note
            elif reduce_size:
                optimization_note = "Per-file size optimization was skipped for the folder; the complete folder was compressed safely."
            result = create_aes256_7z(archive_input, output, password, stored_name=source.name)
            with py7zr.SevenZipFile(output, "r", password=password) as archive:
                archived_names = archive.getnames()
                if (
                    not archive.needs_password()
                    or not archived_names
                    or not all(
                        name == source.name or name.startswith(f"{source.name}/")
                        for name in archived_names
                    )
                ):
                    raise DocumentSecurityError("Encrypted archive validation failed.")
    except Exception:
        output.unlink(missing_ok=True)
        raise

    trashed = False
    note = " ".join(part for part in (optimization_note, result.note) if part)
    if delete_original:
        try:
            send2trash(str(source))
            trashed = True
            note = f"{note} Original moved to Recycle Bin."
        except Exception as exc:
            note = f"{note} Archive is valid, but the original could not be moved to Recycle Bin: {exc}"
    return LocalSecurityResult(output, trashed, note)
