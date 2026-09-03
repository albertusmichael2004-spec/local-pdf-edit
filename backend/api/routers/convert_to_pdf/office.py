from __future__ import annotations

from pathlib import Path
from typing import Annotated, Callable

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from backend.api.http_errors import (
    bad_request,
    dependency_unavailable,
)
from backend.api.workspace import RequestWorkspace
from backend.core.errors import (
    ConversionError,
    PDFWorkbenchError,
)
from backend.services.convert_to_pdf.excel_to_pdf import (
    excel_to_pdf,
)
from backend.services.convert_to_pdf.powerpoint_to_pdf import (
    powerpoint_to_pdf,
)
from backend.services.convert_to_pdf.word_to_pdf import (
    word_to_pdf,
)


router = APIRouter()


async def _office_conversion(
    upload: UploadFile,
    fallback_name: str,
    converter: Callable[
        [Path, Path],
        str,
    ],
) -> FileResponse:
    workspace = RequestWorkspace()

    try:
        input_path, filename, _ = (
            await workspace.save_file(
                upload,
                fallback_name,
            )
        )

        output = workspace.output(
            f"{Path(filename).stem}.pdf"
        )

        engine = await run_in_threadpool(
            converter,
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

    except ConversionError as exc:
        workspace.cleanup_on_error()

        if (
            "LibreOffice" in str(exc)
            and "require" in str(exc).lower()
        ):
            raise dependency_unavailable(
                exc
            ) from exc

        raise bad_request(exc) from exc

    except (
        ValueError,
        PDFWorkbenchError,
    ) as exc:
        workspace.cleanup_on_error()
        raise bad_request(exc) from exc

    except Exception:
        workspace.cleanup_on_error()
        raise


@router.post("/word-to-pdf")
async def api_word_to_pdf(
    file: Annotated[
        UploadFile,
        File(...),
    ],
) -> FileResponse:
    return await _office_conversion(
        file,
        "document.docx",
        word_to_pdf,
    )


@router.post("/powerpoint-to-pdf")
async def api_powerpoint_to_pdf(
    file: Annotated[
        UploadFile,
        File(...),
    ],
) -> FileResponse:
    return await _office_conversion(
        file,
        "presentation.pptx",
        powerpoint_to_pdf,
    )


@router.post("/excel-to-pdf")
async def api_excel_to_pdf(
    file: Annotated[
        UploadFile,
        File(...),
    ],
) -> FileResponse:
    return await _office_conversion(
        file,
        "workbook.xlsx",
        excel_to_pdf,
    )
