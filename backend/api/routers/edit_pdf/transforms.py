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
from backend.services.edit_pdf.crop_pdf import crop_pages, crop_pages_with_plan
from backend.services.edit_pdf.rotate_pdf import rotate_pages, rotate_pages_with_plan
from backend.services.shared.pdf_reader import get_pdf_page_count

from .helpers import all_or_selection


router = APIRouter()


@router.post("/rotate")
async def api_rotate(
    file: Annotated[UploadFile, File(...)],
    pages: Annotated[str, Form()] = "all",
    angle: Annotated[int, Form()] = 90,
    rotation_plan_json: Annotated[str | None, Form()] = None,
) -> FileResponse:
    workspace = RequestWorkspace()
    try:
        input_path, filename, _ = await workspace.save_pdf(file)
        total = get_pdf_page_count(input_path)
        indexes = all_or_selection(pages, total)
        output = workspace.output(f"{Path(filename).stem}_rotated.pdf")
        if rotation_plan_json:
            try:
                payload = json.loads(rotation_plan_json)
                if not isinstance(payload, dict):
                    raise ValueError("Rotation plan must be an object.")
                plan = {int(page) - 1: int(degrees) for page, degrees in payload.items()}
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError("Rotation plan is not valid JSON.") from exc
            await run_in_threadpool(rotate_pages_with_plan, input_path, output, plan)
        else:
            await run_in_threadpool(rotate_pages, input_path, output, set(range(total)) if indexes is None else indexes, angle)
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
    crop_plan_json: Annotated[str | None, Form()] = None,
) -> FileResponse:
    workspace = RequestWorkspace()
    try:
        input_path, filename, _ = await workspace.save_pdf(file)
        total = get_pdf_page_count(input_path)
        indexes = all_or_selection(pages, total)
        output = workspace.output(f"{Path(filename).stem}_cropped.pdf")
        if crop_plan_json:
            try:
                payload = json.loads(crop_plan_json)
                if not isinstance(payload, dict):
                    raise ValueError("Crop plan must be an object.")
                plan = {
                    int(page) - 1: (
                        float(margins["left_mm"]),
                        float(margins["top_mm"]),
                        float(margins["right_mm"]),
                        float(margins["bottom_mm"]),
                    )
                    for page, margins in payload.items()
                }
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError("Crop plan is not valid JSON.") from exc
            await run_in_threadpool(crop_pages_with_plan, input_path, output, plan)
        else:
            await run_in_threadpool(crop_pages, input_path, output, left_mm, top_mm, right_mm, bottom_mm, indexes)
        return workspace.download(output, "application/pdf", output.name)
    except (ValueError, PDFWorkbenchError) as exc:
        workspace.cleanup_on_error()
        raise bad_request(exc) from exc
    except Exception:
        workspace.cleanup_on_error()
        raise
