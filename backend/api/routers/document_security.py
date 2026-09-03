from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Callable

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from starlette.concurrency import run_in_threadpool

from backend.api.http_errors import bad_request
from backend.api.workspace import RequestWorkspace
from backend.core.errors import PDFWorkbenchError
from backend.services.document_security.archive_decryption import decrypt_archive
from backend.services.document_security.archive_extraction import extract_archive_any
from backend.services.document_security.local_operations import unique_path
from backend.services.document_security.archive_security import (
    ArchiveBuildResult,
    create_7z_archive,
    create_aes256_7z,
    create_password_protected_zip,
)
from backend.services.shared.file_hash import sha256_stream
from backend.utils.file_uploads import safe_filename


router = APIRouter(prefix="/document-security")
ArchiveBuilder = Callable[..., ArchiveBuildResult]


def _archive_stem(filename: str) -> str:
    lower = filename.lower()
    for suffix in (
        ".tar.gz", ".tar.bz2", ".tar.xz", ".tbz2", ".txz", ".zip",
        ".7z", ".rar", ".tgz", ".tar", ".gz", ".bz2", ".xz", ".cab",
    ):
        if lower.endswith(suffix):
            return filename[:-len(suffix)] or "archive"
    return Path(filename).stem or "archive"


def _downloads_root() -> Path:
    return Path.home() / "Downloads"


@router.post("/extract-upload")
async def extract_uploaded_archive(
    file: Annotated[UploadFile, File(...)],
    password: Annotated[str, Form()] = "",
) -> JSONResponse:
    workspace = RequestWorkspace()
    destination: Path | None = None
    try:
        input_path, filename, _ = await workspace.save_file(file, "archive.bin")
        downloads = _downloads_root()
        downloads.mkdir(parents=True, exist_ok=True)
        destination = unique_path(downloads, f"{_archive_stem(filename)}_extracted")
        result = await run_in_threadpool(extract_archive_any, input_path, destination, password)
        workspace.cleanup()
        explorer_opened = False
        if os.name == "nt":
            try:
                os.startfile(str(result.destination))
                explorer_opened = True
            except OSError:
                pass
        return JSONResponse({
            "path": str(result.destination),
            "files": result.file_count,
            "bytes": result.total_bytes,
            "type": result.archive_type,
            "explorer_opened": explorer_opened,
        })
    except (ValueError, PDFWorkbenchError) as exc:
        workspace.cleanup_on_error()
        raise bad_request(exc) from exc
    except Exception:
        workspace.cleanup_on_error()
        raise


@router.post("/sha256")
async def sha256(file: Annotated[UploadFile, File(...)]) -> JSONResponse:
    try:
        filename = safe_filename(file.filename, "document.bin")
        digest, size = await run_in_threadpool(
            sha256_stream,
            file.file,
            total=int(file.size or 0),
            label=filename,
        )
        return JSONResponse({"name": filename, "bytes": size, "sha256": digest})
    except (ValueError, PDFWorkbenchError) as exc:
        raise bad_request(exc) from exc
    finally:
        await file.close()


@router.post("/sha256-compare")
async def sha256_compare(
    left: Annotated[UploadFile, File(...)],
    right: Annotated[UploadFile, File(...)],
) -> JSONResponse:
    try:
        left_name = safe_filename(left.filename, "left-file.bin")
        right_name = safe_filename(right.filename, "right-file.bin")
        left_hash, left_size = await run_in_threadpool(
            sha256_stream,
            left.file,
            total=int(left.size or 0),
            label=left_name,
            stage="Hashing first file",
            start=5,
            end=47,
        )
        right_hash, right_size = await run_in_threadpool(
            sha256_stream,
            right.file,
            total=int(right.size or 0),
            label=right_name,
            stage="Hashing second file",
            start=50,
            end=92,
        )
        return JSONResponse({
            "identical": left_hash == right_hash,
            "left": {"name": left_name, "bytes": left_size, "sha256": left_hash},
            "right": {"name": right_name, "bytes": right_size, "sha256": right_hash},
        })
    except (ValueError, PDFWorkbenchError) as exc:
        raise bad_request(exc) from exc
    finally:
        await left.close()
        await right.close()


async def _build_archive(
    upload: UploadFile,
    builder: ArchiveBuilder,
    output_suffix: str,
    media_type: str,
    password: str | None = None,
    reduce_size: bool = False,
) -> FileResponse:
    workspace = RequestWorkspace()
    try:
        input_path, filename, _ = await workspace.save_file(upload, "document.bin")
        base_name = Path(filename).stem or "document"
        output = workspace.output(f"{base_name}{output_suffix}")
        archive_input = input_path
        optimization_note = ""
        if reduce_size:
            from backend.services.document_security.content_optimization import prepare_balanced_content

            optimized = await run_in_threadpool(
                prepare_balanced_content,
                input_path,
                workspace.path / "balanced",
                filename,
            )
            archive_input = optimized.path
            optimization_note = optimized.note
        options = {"stored_name": filename}
        if password is None:
            result = await run_in_threadpool(builder, archive_input, output, **options)
        else:
            result = await run_in_threadpool(builder, archive_input, output, password, **options)
        headers = {
            "X-Archive-Mode": result.mode,
            "X-Archive-Note": " ".join(
                part for part in (optimization_note, result.note) if part
            ),
        }
        return workspace.download(output, media_type, output.name, headers)
    except (ValueError, PDFWorkbenchError) as exc:
        workspace.cleanup_on_error()
        raise bad_request(exc) from exc
    except Exception:
        workspace.cleanup_on_error()
        raise


@router.post("/all-in-one")
async def all_in_one(
    file: Annotated[UploadFile, File(...)],
    password: Annotated[str, Form()],
    reduce_size: Annotated[bool, Form()] = False,
) -> FileResponse:
    return await _build_archive(
        file,
        create_aes256_7z,
        "_secured.7z",
        "application/x-7z-compressed",
        password,
        reduce_size,
    )


@router.post("/password-protect")
async def password_protect(
    file: Annotated[UploadFile, File(...)],
    password: Annotated[str, Form()],
) -> FileResponse:
    return await _build_archive(
        file,
        create_password_protected_zip,
        "_protected.zip",
        "application/zip",
        password,
    )


@router.post("/create-7z")
async def create_7z(file: Annotated[UploadFile, File(...)]) -> FileResponse:
    return await _build_archive(
        file,
        create_7z_archive,
        "_archive.7z",
        "application/x-7z-compressed",
    )


@router.post("/aes256")
async def aes256_encrypt(
    file: Annotated[UploadFile, File(...)],
    password: Annotated[str, Form()],
) -> FileResponse:
    return await _build_archive(
        file,
        create_aes256_7z,
        "_aes256.7z",
        "application/x-7z-compressed",
        password,
    )


@router.post("/decrypt")
async def decrypt(
    file: Annotated[UploadFile, File(...)],
    password: Annotated[str, Form()],
) -> FileResponse:
    workspace = RequestWorkspace()
    try:
        input_path, filename, _ = await workspace.save_file(file, "encrypted.archive")
        result = await run_in_threadpool(
            decrypt_archive,
            input_path,
            workspace.path,
            password,
            archive_stem=Path(filename).stem or "document",
        )
        return workspace.download(
            result.path,
            result.media_type,
            result.download_name,
            {"X-Decrypted-Files": str(result.file_count)},
        )
    except (ValueError, PDFWorkbenchError) as exc:
        workspace.cleanup_on_error()
        raise bad_request(exc) from exc
    except Exception:
        workspace.cleanup_on_error()
        raise
