from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse

from backend.api.http_errors import bad_request
from backend.api.workspace import RequestWorkspace
from backend.core.errors import PDFWorkbenchError
from backend.services.edit_pdf.crop_pdf import crop_pages
from backend.services.edit_pdf.rotate_pdf import rotate_pages
from backend.services.shared.pdf_reader import get_pdf_page_count

from .helpers import all_or_selection


router = APIRouter()


@router.post("/rotate")
async def api_rotate(
    file: Annotated[UploadFile, File(...)],
    pages: Annotated[str, Form()] = "all",
    angle: Annotated[int, Form()] = 90,
) -> FileResponse:
    workspace = RequestWorkspace()
    try:
        input_path, filename, _ = await workspace.save_pdf(file)
        total = get_pdf_page_count(input_path)
        indexes = all_or_selection(pages, total)
        output = workspace.output(f"{Path(filename).stem}_rotated.pdf")
        rotate_pages(input_path, output, set(range(total)) if indexes is None else indexes, angle)
        return workspace.download(output, "application/pdf", output.name)
    except (ValueError, PDFWorkbenchError) as exc:
        workspace.cleanup_on_error()
        raise bad_request(exc) from exc
    except Exception:
        workspace.cleanup_on_error()
        raise


@router.post("/crop")
async def api_crop(
    file: Annotated[UploadFile, File(...)],
    left_mm: Annotated[float, Form()] = 0,
    top_mm: Annotated[float, Form()] = 0,
    right_mm: Annotated[float, Form()] = 0,
    bottom_mm: Annotated[float, Form()] = 0,
    pages: Annotated[str, Form()] = "all",
) -> FileResponse:
    workspace = RequestWorkspace()
    try:
        input_path, filename, _ = await workspace.save_pdf(file)
        indexes = all_or_selection(pages, get_pdf_page_count(input_path))
        output = workspace.output(f"{Path(filename).stem}_cropped.pdf")
        crop_pages(input_path, output, left_mm, top_mm, right_mm, bottom_mm, indexes)
        return workspace.download(output, "application/pdf", output.name)
    except (ValueError, PDFWorkbenchError) as exc:
        workspace.cleanup_on_error()
        raise bad_request(exc) from exc
    except Exception:
        workspace.cleanup_on_error()
        raise
