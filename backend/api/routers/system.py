from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, File, Form, UploadFile
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from backend.api.http_errors import bad_request
from backend.api.workspace import RequestWorkspace, cleanup_orphaned_workspaces
from backend.api.workflow_input import resolve_pdf_input
from backend.core.config import settings
from backend.core.errors import PDFWorkbenchError
from backend.core.progress import registry
from backend.core.preferences import read_locale, write_locale
from backend.core.update import check_for_update
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
from backend.services.workflow_session import workflow_store


router = APIRouter()


@router.get("/progress/{job_id}")
def progress(job_id: str) -> JSONResponse:
    return JSONResponse(registry.snapshot(job_id) or {"status": "pending"})


@router.post("/workspace/reset")
def reset_workspace() -> JSONResponse:
    """Clean abandoned temporary workspaces before the next UI task."""
    removed = cleanup_orphaned_workspaces()
    removed_workflows = workflow_store.cleanup_all()
    registry.clear()
    return JSONResponse({
        "status": "reset",
        "removed_workspaces": removed,
        "removed_workflows": removed_workflows,
    })


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
        "workflow_ttl_seconds": workflow_store.ttl_seconds,
    })


@router.get("/update/check")
def update_check() -> JSONResponse:
    return JSONResponse(check_for_update())


@router.get("/preferences/language")
def get_language_preference() -> JSONResponse:
    return JSONResponse({"language": read_locale()})


@router.put("/preferences/language")
def set_language_preference(payload: dict[str, object] = Body(...)) -> JSONResponse:
    try:
        language = write_locale(str(payload.get("language", "")))
    except (AttributeError, TypeError, ValueError) as exc:
        raise bad_request(exc) from exc
    return JSONResponse({"language": language})


@router.post("/pdf/info")
async def pdf_info(
    file: Annotated[UploadFile | None, File()] = None,
    workflow_id: Annotated[str | None, Form()] = None,
    artifact_id: Annotated[str | None, Form()] = None,
) -> JSONResponse:
    workspace = RequestWorkspace()
    try:
        input_path, filename, size = await resolve_pdf_input(
            workspace, file, workflow_id, artifact_id
        )
        pages = await run_in_threadpool(get_pdf_page_count, input_path)
        return JSONResponse({"name": filename, "bytes": size, "pages": pages})
    except (ValueError, PDFWorkbenchError) as exc:
        raise bad_request(exc) from exc
    finally:
        workspace.cleanup()


@router.post("/pdf/previews")
async def pdf_previews(
    file: Annotated[UploadFile | None, File()] = None,
    pages: Annotated[str, Form()] = "1",
    workflow_id: Annotated[str | None, Form()] = None,
    artifact_id: Annotated[str | None, Form()] = None,
    max_width: Annotated[int, Form()] = 440,
) -> JSONResponse:
    workspace = RequestWorkspace()
    try:
        input_path, filename, size = await resolve_pdf_input(
            workspace, file, workflow_id, artifact_id
        )
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
        render_width = min(3200, max(240, max_width))
        previews = await run_in_threadpool(
            lambda: [render_page_preview(input_path, page, max_width=render_width) for page in requested[:24]]
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
