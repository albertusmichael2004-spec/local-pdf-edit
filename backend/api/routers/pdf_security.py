from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from starlette.concurrency import run_in_threadpool

from backend.api.http_errors import bad_request
from backend.api.workspace import RequestWorkspace
from backend.core.errors import PDFWorkbenchError
from backend.services.pdf_security.compare_pdf import compare_pdfs_detailed, compare_pdfs_to_zip
from backend.services.pdf_security.protect_pdf import protect_pdf
from backend.services.shared.file_hash import sha256_stream
from backend.services.pdf_security.unlock_pdf import unlock_pdf
from backend.utils.file_uploads import safe_filename


router = APIRouter(prefix="/security")


@router.post("/unlock")
async def api_unlock(
    file: Annotated[UploadFile, File(...)],
    password: Annotated[str, Form()] = "",
) -> FileResponse:
    workspace = RequestWorkspace()
    try:
        input_path, filename, _ = await workspace.save_pdf(file)
        output = workspace.output(f"{Path(filename).stem}_unlocked.pdf")
        count = await run_in_threadpool(unlock_pdf, input_path, output, password)
        return workspace.download(output, "application/pdf", output.name, {"X-PDF-Pages": str(count)})
    except (ValueError, PDFWorkbenchError) as exc:
        workspace.cleanup_on_error()
        raise bad_request(exc) from exc
    except Exception:
        workspace.cleanup_on_error()
        raise


@router.post("/protect")
async def api_protect(
    file: Annotated[UploadFile, File(...)],
    password: Annotated[str, Form()],
) -> FileResponse:
    workspace = RequestWorkspace()
    try:
        input_path, filename, _ = await workspace.save_pdf(file)
        output = workspace.output(f"{Path(filename).stem}_protected.pdf")
        count = await run_in_threadpool(protect_pdf, input_path, output, password)
        return workspace.download(output, "application/pdf", output.name, {"X-PDF-Pages": str(count)})
    except (ValueError, PDFWorkbenchError) as exc:
        workspace.cleanup_on_error()
        raise bad_request(exc) from exc
    except Exception:
        workspace.cleanup_on_error()
        raise


@router.post("/sha256")
async def api_sha256(file: Annotated[UploadFile, File(...)]) -> JSONResponse:
    try:
        filename = safe_filename(file.filename, "document.pdf")
        digest, size = await run_in_threadpool(
            sha256_stream,
            file.file,
            total=int(file.size or 0),
            label=filename,
            require_pdf=True,
        )
        return JSONResponse({"name": filename, "bytes": size, "sha256": digest})
    except (ValueError, PDFWorkbenchError) as exc:
        raise bad_request(exc) from exc
    finally:
        await file.close()


@router.post("/sha256-compare")
async def api_sha256_compare(
    left: Annotated[UploadFile, File(...)],
    right: Annotated[UploadFile, File(...)],
) -> JSONResponse:
    try:
        left_name = safe_filename(left.filename, "left.pdf")
        right_name = safe_filename(right.filename, "right.pdf")
        left_hash, _ = await run_in_threadpool(
            sha256_stream, left.file, total=int(left.size or 0), label=left_name,
            require_pdf=True, stage="Hashing first PDF", start=5, end=47,
        )
        right_hash, _ = await run_in_threadpool(
            sha256_stream, right.file, total=int(right.size or 0), label=right_name,
            require_pdf=True, stage="Hashing second PDF", start=50, end=92,
        )
        identical = left_hash == right_hash
        return JSONResponse({
            "identical": identical,
            "left": {"name": left_name, "sha256": left_hash},
            "right": {"name": right_name, "sha256": right_hash},
        })
    except (ValueError, PDFWorkbenchError) as exc:
        raise bad_request(exc) from exc
    finally:
        await left.close()
        await right.close()


@router.post("/compare-pdf-summary")
async def api_compare_pdf_summary(
    left: Annotated[UploadFile, File(...)],
    right: Annotated[UploadFile, File(...)],
) -> JSONResponse:
    workspace = RequestWorkspace()
    try:
        left_path, left_name, _ = await workspace.save_pdf(left, "left.pdf")
        right_path, right_name, _ = await workspace.save_pdf(right, "right.pdf", prefix="right_")
        summary, _ = await run_in_threadpool(
            compare_pdfs_detailed, left_path, right_path, include_diff_payloads=False
        )
        summary["left_name"] = left_name
        summary["right_name"] = right_name
        return JSONResponse(summary)
    except (ValueError, PDFWorkbenchError) as exc:
        raise bad_request(exc) from exc
    finally:
        workspace.cleanup()


@router.post("/compare-pdf")
async def api_compare_pdf(
    left: Annotated[UploadFile, File(...)],
    right: Annotated[UploadFile, File(...)],
) -> FileResponse:
    workspace = RequestWorkspace()
    try:
        left_path, _, _ = await workspace.save_pdf(left, "left.pdf")
        right_path, _, _ = await workspace.save_pdf(right, "right.pdf", prefix="right_")
        output = workspace.output("pdf_comparison_report.zip")
        summary = await run_in_threadpool(compare_pdfs_to_zip, left_path, right_path, output)
        headers = {
            "X-Byte-Identical": "true" if summary.get("byte_identical") else "false",
            "X-Different-Pages": str(summary.get("different_pages", 0)),
        }
        return workspace.download(output, "application/zip", output.name, headers)
    except (ValueError, PDFWorkbenchError) as exc:
        workspace.cleanup_on_error()
        raise bad_request(exc) from exc
    except Exception:
        workspace.cleanup_on_error()
        raise
