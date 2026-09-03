from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from backend.api.http_errors import bad_request
from backend.api.workspace import RequestWorkspace
from backend.core.config import settings
from backend.core.errors import PDFWorkbenchError
from backend.core.progress import registry
from backend.core.executables import (
    find_ebook_convert,
    find_ffmpeg,
    find_ffprobe,
    find_ghostscript,
    find_libreoffice,
    find_tesseract,
)
from backend.services.shared.pdf_reader import get_pdf_page_count
from backend.services.shared.preview import render_page_preview


router = APIRouter()


@router.get("/progress/{job_id}")
def progress(job_id: str) -> JSONResponse:
    return JSONResponse(registry.snapshot(job_id) or {"status": "pending"})


@router.get("/health")
def health() -> JSONResponse:
    return JSONResponse({
        "status": "ok",
        "app": settings.app_name,
        "ghostscript": find_ghostscript(),
        "tesseract": find_tesseract(),
        "libreoffice": find_libreoffice(),
        "ffmpeg": find_ffmpeg(),
        "ffprobe": find_ffprobe(),
        "calibre": find_ebook_convert(),
        "upload_limit": None,
        "max_archive_output_mb": None,
        "privacy": "localhost-only; no cloud upload",
    })


@router.post("/pdf/info")
async def pdf_info(file: Annotated[UploadFile, File(...)]) -> JSONResponse:
    workspace = RequestWorkspace()
    try:
        input_path, filename, size = await workspace.save_pdf(file)
        pages = await run_in_threadpool(get_pdf_page_count, input_path)
        return JSONResponse({"name": filename, "bytes": size, "pages": pages})
    except (ValueError, PDFWorkbenchError) as exc:
        raise bad_request(exc) from exc
    finally:
        workspace.cleanup()


@router.post("/pdf/previews")
async def pdf_previews(
    file: Annotated[UploadFile, File(...)],
    pages: Annotated[str, Form()] = "1",
) -> JSONResponse:
    workspace = RequestWorkspace()
    try:
        input_path, filename, size = await workspace.save_pdf(file)
        total_pages = await run_in_threadpool(get_pdf_page_count, input_path)
        requested: list[int] = []
        for raw_value in pages.split(","):
            value = raw_value.strip()
            if not value:
                continue
            page = int(value)
            if page < 1 or page > total_pages:
                raise ValueError(f"Page {page} is outside 1-{total_pages}.")
            if page not in requested:
                requested.append(page)
        if not requested:
            requested = [1]
        previews = await run_in_threadpool(
            lambda: [render_page_preview(input_path, page) for page in requested[:24]]
        )
        return JSONResponse({
            "name": filename,
            "bytes": size,
            "pages": total_pages,
            "previews": [
                {
                    "page": preview.page,
                    "image": preview.image,
                    "width_pt": preview.width_pt,
                    "height_pt": preview.height_pt,
                    "rotation": preview.rotation,
                }
                for preview in previews
            ],
        })
    except (ValueError, PDFWorkbenchError) as exc:
        raise bad_request(exc) from exc
    finally:
        workspace.cleanup()
