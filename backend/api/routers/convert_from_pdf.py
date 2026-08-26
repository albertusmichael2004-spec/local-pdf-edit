from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse

from backend.api.http_errors import bad_request
from backend.api.workspace import RequestWorkspace
from backend.core.errors import PDFWorkbenchError
from backend.services.convert_from_pdf.pdf_to_excel import pdf_to_xlsx
from backend.services.convert_from_pdf.pdf_to_jpg import pdf_to_jpg_zip
from backend.services.convert_from_pdf.pdf_to_powerpoint import pdf_to_pptx
from backend.services.convert_from_pdf.pdf_to_word import pdf_to_docx
from backend.services.shared.pdf_reader import get_pdf_page_count


router = APIRouter(prefix="/convert")


@router.post("/pdf-to-jpg")
async def api_pdf_to_jpg(file: Annotated[UploadFile, File(...)]) -> FileResponse:
    workspace = RequestWorkspace()
    try:
        input_path, filename, _ = await workspace.save_pdf(file)
        output = workspace.output(f"{Path(filename).stem}_jpg.zip")
        count = pdf_to_jpg_zip(input_path, output)
        return workspace.download(output, "application/zip", output.name, {"X-Image-Count": str(count)})
    except (ValueError, PDFWorkbenchError) as exc:
        workspace.cleanup_on_error()
        raise bad_request(exc) from exc
    except Exception:
        workspace.cleanup_on_error()
        raise


@router.post("/pdf-to-word")
async def api_pdf_to_word(file: Annotated[UploadFile, File(...)]) -> FileResponse:
    workspace = RequestWorkspace()
    try:
        input_path, filename, _ = await workspace.save_pdf(file)
        get_pdf_page_count(input_path)
        output = workspace.output(f"{Path(filename).stem}.docx")
        pdf_to_docx(input_path, output)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        return workspace.download(output, media_type, output.name)
    except (ValueError, PDFWorkbenchError) as exc:
        workspace.cleanup_on_error()
        raise bad_request(exc) from exc
    except Exception:
        workspace.cleanup_on_error()
        raise


@router.post("/pdf-to-powerpoint")
async def api_pdf_to_powerpoint(file: Annotated[UploadFile, File(...)]) -> FileResponse:
    workspace = RequestWorkspace()
    try:
        input_path, filename, _ = await workspace.save_pdf(file)
        output = workspace.output(f"{Path(filename).stem}.pptx")
        count = pdf_to_pptx(input_path, output)
        media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        return workspace.download(output, media_type, output.name, {"X-Slides": str(count)})
    except (ValueError, PDFWorkbenchError) as exc:
        workspace.cleanup_on_error()
        raise bad_request(exc) from exc
    except Exception:
        workspace.cleanup_on_error()
        raise


@router.post("/pdf-to-excel")
async def api_pdf_to_excel(file: Annotated[UploadFile, File(...)]) -> FileResponse:
    workspace = RequestWorkspace()
    try:
        input_path, filename, _ = await workspace.save_pdf(file)
        output = workspace.output(f"{Path(filename).stem}.xlsx")
        sheets, tables = pdf_to_xlsx(input_path, output)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return workspace.download(
            output,
            media_type,
            output.name,
            {"X-Sheets": str(sheets), "X-Tables": str(tables)},
        )
    except (ValueError, PDFWorkbenchError) as exc:
        workspace.cleanup_on_error()
        raise bad_request(exc) from exc
    except Exception:
        workspace.cleanup_on_error()
        raise
