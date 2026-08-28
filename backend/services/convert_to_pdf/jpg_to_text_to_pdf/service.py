from __future__ import annotations

from pathlib import Path

from backend.core.errors import ConversionError, OCRError
from backend.core.executables import find_tesseract

from .docx_exporter import export_docx
from .ocr_runner import recognize_images
from .pdf_exporter import export_pdf

VALID_OUTPUT_FORMATS = {"pdf", "docx"}
VALID_QUALITY_MODES = {"fast", "accurate", "maximum"}
VALID_LAYOUT_MODES = {"preserve", "editable"}


def _normalize(value: str) -> str:
    return value.strip().lower()


def _validate(image_paths: list[Path], output_format: str, quality: str, layout_mode: str) -> None:
    if not image_paths:
        raise ConversionError("Upload at least one image.")
    if output_format not in VALID_OUTPUT_FORMATS:
        raise ConversionError("Output format must be 'pdf' or 'docx'.")
    if quality not in VALID_QUALITY_MODES:
        raise ConversionError("OCR quality must be 'fast', 'accurate', or 'maximum'.")
    if layout_mode not in VALID_LAYOUT_MODES:
        raise ConversionError("Layout mode must be 'preserve' or 'editable'.")


def jpg_to_text_to_pdf_or_word(
    image_paths: list[Path],
    output_path: Path,
    output_format: str = "pdf",
    language: str = "auto",
    quality: str = "accurate",
    layout_mode: str = "preserve",
) -> int:
    """Recognize ordered images and export one PDF/Word page per source image."""
    output_format = _normalize(output_format)
    quality = _normalize(quality)
    layout_mode = _normalize(layout_mode)
    language = language.strip() or "auto"
    _validate(image_paths, output_format, quality, layout_mode)
    tesseract = find_tesseract()
    if not tesseract:
        raise OCRError(
            "Tesseract was not found. Install Tesseract OCR and restart the app, "
            "or set TESSERACT_PATH to the executable."
        )
    pages = recognize_images(image_paths, tesseract, language, quality)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "pdf":
        export_pdf(pages, output_path, layout_mode)
    else:
        export_docx(pages, output_path)
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise ConversionError("OCR export finished but no output file was produced.")
    return len(pages)
