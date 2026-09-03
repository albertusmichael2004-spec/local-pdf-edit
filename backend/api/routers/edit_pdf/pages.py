from __future__ import annotations

from pathlib import Path
import json
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from backend.api.http_errors import bad_request
from backend.api.workspace import RequestWorkspace
from backend.core.errors import PDFWorkbenchError
from backend.services.edit_pdf.extract_pages import extract_pages
from backend.services.edit_pdf.organize_pdf import organize_pages, organize_with_plan
from backend.services.edit_pdf.remove_pages import remove_pages
from backend.services.shared.pdf_reader import get_pdf_page_count
from backend.utils.page_ranges import parse_page_selection


router = APIRouter()


def _handle_known_error(workspace: RequestWorkspace, exc: Exception):
    workspace.cleanup_on_error()
    raise bad_request(exc) from exc


@router.post("/remove-pages")
async def api_remove_pages(
    file: Annotated[UploadFile, File(...)],
    pages: Annotated[str, Form()],
) -> FileResponse:
    workspace = RequestWorkspace()
    try:
        input_path, filename, _ = await workspace.save_pdf(file)
        selected = parse_page_selection(pages, get_pdf_page_count(input_path))
        output = workspace.output(f"{Path(filename).stem}_pages_removed.pdf")
        kept = await run_in_threadpool(remove_pages, input_path, output, {page - 1 for page in selected})
        return workspace.download(output, "application/pdf", output.name, {"X-Output-Pages": str(kept)})
    except (ValueError, PDFWorkbenchError) as exc:
        _handle_known_error(workspace, exc)
    except Exception:
        workspace.cleanup_on_error()
        raise


@router.post("/extract-pages")
async def api_extract_pages(
    file: Annotated[UploadFile, File(...)],
    pages: Annotated[str, Form()],
) -> FileResponse:
    workspace = RequestWorkspace()
    try:
        input_path, filename, _ = await workspace.save_pdf(file)
        selected = parse_page_selection(pages, get_pdf_page_count(input_path))
        output = workspace.output(f"{Path(filename).stem}_extracted.pdf")
        count = await run_in_threadpool(extract_pages, input_path, output, [page - 1 for page in selected])
        return workspace.download(output, "application/pdf", output.name, {"X-Output-Pages": str(count)})
    except (ValueError, PDFWorkbenchError) as exc:
        _handle_known_error(workspace, exc)
    except Exception:
        workspace.cleanup_on_error()
        raise


@router.post("/organize")
async def api_organize(
    file: Annotated[UploadFile, File(...)],
    order: Annotated[str, Form()] = "",
    plan_json: Annotated[str | None, Form()] = None,
) -> FileResponse:
    workspace = RequestWorkspace()
    try:
        input_path, filename, _ = await workspace.save_pdf(file)
        output = workspace.output(f"{Path(filename).stem}_organized.pdf")
        if plan_json:
            try:
                plan = json.loads(plan_json)
            except json.JSONDecodeError as exc:
                raise ValueError("The page editor plan is not valid JSON.") from exc
            if not isinstance(plan, list):
                raise ValueError("The page editor plan must be a list.")
            count = await run_in_threadpool(organize_with_plan, input_path, output, plan)
        else:
            if not order.strip():
                raise ValueError("Enter a page order or arrange pages in the visual editor.")
            selected = parse_page_selection(order, get_pdf_page_count(input_path))
            count = await run_in_threadpool(organize_pages, input_path, output, [page - 1 for page in selected])
        return workspace.download(output, "application/pdf", output.name, {"X-Output-Pages": str(count)})
    except (ValueError, PDFWorkbenchError) as exc:
        _handle_known_error(workspace, exc)
    except Exception:
        workspace.cleanup_on_error()
        raise
