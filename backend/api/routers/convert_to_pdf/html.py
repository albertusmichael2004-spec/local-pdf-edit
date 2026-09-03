from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from backend.api.http_errors import bad_request
from backend.api.workspace import RequestWorkspace
from backend.core.errors import PDFWorkbenchError
from backend.services.convert_to_pdf.html_to_pdf import html_to_pdf


router = APIRouter()


@router.post("/html-to-pdf")
async def api_html_to_pdf(
    file: Annotated[
        UploadFile,
        File(...),
    ],
) -> FileResponse:
    workspace = RequestWorkspace()

    try:
        input_path, filename, _ = await workspace.save_file(
            file,
            "page.html",
        )

        output = workspace.output(
            f"{Path(filename).stem}.pdf"
        )

        engine = await run_in_threadpool(
            html_to_pdf,
            input_path,
            output,
        )

        return workspace.download(
            output,
            "application/pdf",
            output.name,
            {
                "X-Conversion-Engine": engine,
            },
        )

    except (
        ValueError,
        PDFWorkbenchError,
    ) as exc:
        workspace.cleanup_on_error()
        raise bad_request(exc) from exc

    except Exception:
        workspace.cleanup_on_error()
        raise
