from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse

from backend.api.http_errors import bad_request
from backend.api.workspace import RequestWorkspace
from backend.core.errors import PDFWorkbenchError
from backend.services.convert_to_pdf.jpg_to_text_to_pdf import jpg_to_text_to_pdf_or_word

router = APIRouter()


@router.post("/image-ocr-export")
async def api_image_ocr_export(
    files: Annotated[list[UploadFile], File(...)],
    output_format: Annotated[str, Form()] = "pdf",
    language: Annotated[str, Form()] = "auto",
    quality: Annotated[str, Form()] = "accurate",
    layout_mode: Annotated[str, Form()] = "preserve",
) -> FileResponse:
    workspace = RequestWorkspace()
    try:
        normalized_format = output_format.lower().strip()
        if normalized_format not in {"pdf", "docx"}:
            raise ValueError("Output format must be PDF or Word.")
        if not files:
            raise ValueError("Upload at least one image.")
        image_paths: list[Path] = []
        for index, upload in enumerate(files, start=1):
            path, _, _ = await workspace.save_file(
                upload,
                fallback=f"image_{index}.jpg",
                prefix=f"{index:03d}_",
            )
            image_paths.append(path)
        extension = "pdf" if normalized_format == "pdf" else "docx"
        output = workspace.output(f"image_ocr_text.{extension}")
        image_count = jpg_to_text_to_pdf_or_word(
            image_paths=image_paths,
            output_path=output,
            output_format=normalized_format,
            language=language,
            quality=quality,
            layout_mode=layout_mode,
        )
        media_type = (
            "application/pdf"
            if normalized_format == "pdf"
            else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        return workspace.download(output, media_type, output.name, {
            "X-Image-Count": str(image_count),
            "X-Conversion-Engine": "Tesseract OCR",
            "X-OCR-Quality": quality,
            "X-OCR-Layout": layout_mode,
        })
    except (ValueError, PDFWorkbenchError) as exc:
        workspace.cleanup_on_error()
        raise bad_request(exc) from exc
    except Exception:
        workspace.cleanup_on_error()
        raise
