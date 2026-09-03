from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from backend.api.http_errors import bad_request
from backend.api.workspace import RequestWorkspace
from backend.core.errors import PDFWorkbenchError
from backend.services.convert_to_pdf.jpg_to_pdf import (
    jpg_to_pdf,
)


router = APIRouter()


@router.post("/jpg-to-pdf")
async def api_jpg_to_pdf(
    files: Annotated[
        list[UploadFile],
        File(...),
    ],
) -> FileResponse:
    workspace = RequestWorkspace()

    try:
        paths: list[Path] = []

        for index, upload in enumerate(
            files,
            start=1,
        ):
            path, _, _ = await workspace.save_file(
                upload,
                fallback=f"image_{index}.jpg",
                prefix=f"{index:03d}_",
            )

            paths.append(path)

        output = workspace.output(
            "images.pdf"
        )

        count = await run_in_threadpool(
            jpg_to_pdf,
            paths,
            output,
        )

        return workspace.download(
            output,
            "application/pdf",
            "images.pdf",
            {
                "X-Image-Count": str(count),
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
