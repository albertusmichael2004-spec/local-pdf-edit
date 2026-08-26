from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from backend.api.http_errors import bad_request
from backend.api.workspace import RequestWorkspace
from backend.core.errors import PDFWorkbenchError
from backend.services.pdf_security.compare_pdf import compare_pdfs_detailed, compare_pdfs_to_zip
from backend.services.pdf_security.compare_sha256 import compare_sha256
from backend.services.pdf_security.protect_pdf import protect_pdf
from backend.services.pdf_security.sha256_pdf import sha256_file
from backend.services.pdf_security.unlock_pdf import unlock_pdf


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
        count = unlock_pdf(input_path, output, password)
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
        count = protect_pdf(input_path, output, password)
        return workspace.download(output, "application/pdf", output.name, {"X-PDF-Pages": str(count)})
    except (ValueError, PDFWorkbenchError) as exc:
        workspace.cleanup_on_error()
        raise bad_request(exc) from exc
    except Exception:
        workspace.cleanup_on_error()
        raise


@router.post("/sha256")
async def api_sha256(file: Annotated[UploadFile, File(...)]) -> JSONResponse:
    workspace = RequestWorkspace()
    try:
        input_path, filename, size = await workspace.save_pdf(file)
        return JSONResponse({"name": filename, "bytes": size, "sha256": sha256_file(input_path)})
    except (ValueError, PDFWorkbenchError) as exc:
        raise bad_request(exc) from exc
    finally:
        workspace.cleanup()


@router.post("/sha256-compare")
async def api_sha256_compare(
    left: Annotated[UploadFile, File(...)],
    right: Annotated[UploadFile, File(...)],
) -> JSONResponse:
    workspace = RequestWorkspace()
    try:
        left_path, left_name, _ = await workspace.save_pdf(left, "left.pdf")
        right_path, right_name, _ = await workspace.save_pdf(right, "right.pdf", prefix="right_")
        left_hash, right_hash, identical = compare_sha256(left_path, right_path)
        return JSONResponse({
            "identical": identical,
            "left": {"name": left_name, "sha256": left_hash},
            "right": {"name": right_name, "sha256": right_hash},
        })
    except (ValueError, PDFWorkbenchError) as exc:
        raise bad_request(exc) from exc
    finally:
        workspace.cleanup()


@router.post("/compare-pdf-summary")
async def api_compare_pdf_summary(
    left: Annotated[UploadFile, File(...)],
    right: Annotated[UploadFile, File(...)],
) -> JSONResponse:
    workspace = RequestWorkspace()
    try:
        left_path, left_name, _ = await workspace.save_pdf(left, "left.pdf")
        right_path, right_name, _ = await workspace.save_pdf(right, "right.pdf", prefix="right_")
        summary, _ = compare_pdfs_detailed(left_path, right_path, include_diff_payloads=False)
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
        summary = compare_pdfs_to_zip(left_path, right_path, output)
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
