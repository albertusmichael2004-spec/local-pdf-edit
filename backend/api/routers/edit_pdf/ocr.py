from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from backend.api.http_errors import bad_request, dependency_unavailable
from backend.api.workspace import RequestWorkspace
from backend.core.errors import OCRError, PDFWorkbenchError
from backend.services.edit_pdf.ocr_pdf import ocr_pdf


router = APIRouter()


@router.post("/ocr")
async def api_ocr(
    file: Annotated[UploadFile, File(...)],
    language: Annotated[str, Form()] = "eng",
    dpi: Annotated[int, Form()] = 200,
) -> FileResponse:
    workspace = RequestWorkspace()
    try:
        input_path, filename, _ = await workspace.save_pdf(file)
        output = workspace.output(f"{Path(filename).stem}_ocr.pdf")
        count = await run_in_threadpool(ocr_pdf, input_path, output, language, min(300, max(120, dpi)))
        return workspace.download(output, "application/pdf", output.name, {"X-OCR-Pages": str(count)})
    except OCRError as exc:
        workspace.cleanup_on_error()
        if "Tesseract" in str(exc):
            raise dependency_unavailable(exc) from exc
        raise bad_request(exc) from exc
    except (ValueError, PDFWorkbenchError) as exc:
        workspace.cleanup_on_error()
        raise bad_request(exc) from exc
    except Exception:
        workspace.cleanup_on_error()
        raise
