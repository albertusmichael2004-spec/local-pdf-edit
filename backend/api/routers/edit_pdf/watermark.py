from __future__ import annotations

from pathlib import Path
from typing import Annotated
import json

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from starlette.concurrency import run_in_threadpool

import fitz

from backend.api.http_errors import bad_request
from backend.api.workspace import RequestWorkspace
from backend.core.errors import PDFWorkbenchError
from backend.core.paths import custom_font_dir
from backend.services.edit_pdf.add_watermark import WatermarkRule, add_text_watermarks
from backend.services.edit_pdf.watermark_fonts import (
    builtin_fonts,
    custom_fonts,
    safe_font_filename,
)
from backend.services.shared.pdf_reader import get_pdf_page_count
from backend.utils.file_uploads import save_upload
from backend.utils.page_ranges import parse_page_selection


router = APIRouter()


@router.get("/watermark/fonts")
def list_watermark_fonts() -> JSONResponse:
    return JSONResponse({"builtin": builtin_fonts(), "custom": custom_fonts()})


@router.post("/watermark/font")
async def upload_watermark_font(
    file: Annotated[UploadFile, File(...)],
) -> JSONResponse:
    try:
        filename = safe_font_filename(file.filename or "font.ttf")
        destination = custom_font_dir() / filename
        await save_upload(file, destination, require_pdf=False)
        try:
            fitz.Font(fontfile=str(destination))
        except Exception as exc:
            destination.unlink(missing_ok=True)
            raise ValueError("The uploaded file is not a readable TrueType/OpenType font.") from exc
        return JSONResponse({"key": f"custom:{filename}", "label": destination.stem})
    except (ValueError, PDFWorkbenchError) as exc:
        raise bad_request(exc) from exc


def _rule_from_payload(payload: dict, total_pages: int) -> WatermarkRule:
    pages = payload.get("pages", "all")
    if pages == "all" or pages is None:
        indexes = None
    elif isinstance(pages, list):
        numbers = [int(page) for page in pages]
        for page in numbers:
            if page < 1 or page > total_pages:
                raise ValueError(f"Watermark page {page} is outside 1-{total_pages}.")
        indexes = {page - 1 for page in numbers}
    else:
        indexes = {page - 1 for page in parse_page_selection(str(pages), total_pages)}

    return WatermarkRule(
        text=str(payload.get("text", "")),
        pages_zero_based=indexes,
        opacity=float(payload.get("opacity", 0.22)),
        font_size=float(payload.get("font_size", 42)),
        rotation=int(payload.get("rotation", 45)),
        font_key=str(payload.get("font_key", "arial")),
    )


@router.post("/watermark")
async def api_watermark(
    file: Annotated[UploadFile, File(...)],
    rules_json: Annotated[str, Form()] = "[]",
) -> FileResponse:
    workspace = RequestWorkspace()
    try:
        input_path, filename, _ = await workspace.save_pdf(file)
        total_pages = get_pdf_page_count(input_path)
        try:
            payload = json.loads(rules_json)
        except json.JSONDecodeError as exc:
            raise ValueError("Watermark rules are not valid JSON.") from exc
        if not isinstance(payload, list):
            raise ValueError("Watermark rules must be a list.")
        rules = [_rule_from_payload(rule, total_pages) for rule in payload]
        output = workspace.output(f"{Path(filename).stem}_watermarked.pdf")
        await run_in_threadpool(add_text_watermarks, input_path, output, rules)
        return workspace.download(output, "application/pdf", output.name)
    except (ValueError, PDFWorkbenchError) as exc:
        workspace.cleanup_on_error()
        raise bad_request(exc) from exc
    except Exception:
        workspace.cleanup_on_error()
        raise
