from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse

from backend.api.http_errors import bad_request, dependency_unavailable
from backend.api.workspace import RequestWorkspace
from backend.core.config import settings
from backend.core.errors import CompressionError, PDFWorkbenchError
from backend.services.edit_pdf.compress_pdf import compress_preset, compress_to_target_range


router = APIRouter()


@router.post("/compress")
async def compress(
    file: Annotated[UploadFile, File(...)],
    mode: Annotated[str, Form()] = "recommended",
    target_min_mb: Annotated[float | None, Form()] = None,
    target_max_mb: Annotated[float | None, Form()] = None,
) -> FileResponse:
    workspace = RequestWorkspace()
    try:
        input_path, filename, _ = await workspace.save_pdf(file)
        output_name = f"{Path(filename).stem}_compressed.pdf"
        output = workspace.output(output_name)

        if mode == "custom":
            if target_min_mb is None or target_max_mb is None:
                raise ValueError("Custom compression requires minimum and maximum target sizes.")
            if target_min_mb <= 0 or target_max_mb <= 0 or target_min_mb > target_max_mb:
                raise ValueError("Enter a valid custom size range where min <= max and both are > 0.")
            result = compress_to_target_range(
                input_path,
                output,
                int(target_min_mb * 1024 * 1024),
                int(target_max_mb * 1024 * 1024),
                settings.ghostscript_timeout_seconds,
            )
        else:
            result = compress_preset(input_path, output, mode, settings.ghostscript_timeout_seconds)

        headers = {
            "X-Compression-Mode": result.mode,
            "X-Original-Bytes": str(result.original_bytes),
            "X-Output-Bytes": str(result.output_bytes),
            "X-Reduction-Percent": f"{result.reduction_percent:.2f}",
            "X-Compression-Note": result.note[:500],
        }
        if result.achieved_target is not None:
            headers["X-Target-Achieved"] = "true" if result.achieved_target else "false"
        return workspace.download(output, "application/pdf", output_name, headers)
    except CompressionError as exc:
        workspace.cleanup_on_error()
        if "Ghostscript" in str(exc) and "not found" in str(exc):
            raise dependency_unavailable(exc) from exc
        raise bad_request(exc) from exc
    except (ValueError, PDFWorkbenchError) as exc:
        workspace.cleanup_on_error()
        raise bad_request(exc) from exc
    except Exception:
        workspace.cleanup_on_error()
        raise
