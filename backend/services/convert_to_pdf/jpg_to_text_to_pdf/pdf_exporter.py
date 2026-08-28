from __future__ import annotations

from pathlib import Path

from backend.core.errors import ConversionError
from backend.services.shared.ocr.models import OCRPage
from backend.services.shared.ocr.searchable_pdf import render_searchable_pdf

from .text_layout import page_lines


def _wrap_line(text: str, width: float, font_name: str, font_size: float, pdfmetrics) -> list[str]:
    words = text.split()
    if not words:
        return []
    output: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if pdfmetrics.stringWidth(candidate, font_name, font_size) <= width:
            current = candidate
        else:
            output.append(current)
            current = word
    output.append(current)
    return output


def _fit_page(lines: list[str], width: float, height: float, pdfmetrics) -> tuple[float, float, list[str]]:
    font_name = "Helvetica"
    for font_size in (10.0, 9.5, 9.0, 8.5, 8.0, 7.5):
        wrapped = [part for line in lines for part in _wrap_line(line, width, font_name, font_size, pdfmetrics)]
        leading = font_size * 1.35
        if len(wrapped) * leading <= height:
            return font_size, leading, wrapped
    return 7.0, 9.0, [part for line in lines for part in _wrap_line(line, width, font_name, 7.0, pdfmetrics)]


def _export_editable_pdf(pages: list[OCRPage], output_path: Path) -> None:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfgen.canvas import Canvas
    except ImportError as exc:
        raise ConversionError("ReportLab is required for editable PDF export.") from exc
    margin = 42.0
    page_width, page_height = A4
    canvas = Canvas(str(output_path), pagesize=A4)
    canvas.setTitle("OCR text export")
    try:
        for index, page in enumerate(pages):
            lines = page_lines(page) or ["(No text detected on this image.)"]
            font_size, leading, wrapped = _fit_page(
                lines,
                page_width - margin * 2,
                page_height - margin * 2,
                pdfmetrics,
            )
            text = canvas.beginText(margin, page_height - margin - font_size)
            text.setFont("Helvetica", font_size)
            text.setLeading(leading)
            for line in wrapped:
                text.textLine(line)
            canvas.drawText(text)
            if index < len(pages) - 1:
                canvas.showPage()
        canvas.save()
    except Exception as exc:
        raise ConversionError(f"Failed to create editable PDF: {exc}") from exc


def export_pdf(pages: list[OCRPage], output_path: Path, layout_mode: str) -> None:
    normalized_mode = layout_mode.strip().lower()
    if normalized_mode == "preserve":
        render_searchable_pdf(pages, output_path)
    elif normalized_mode == "editable":
        _export_editable_pdf(pages, output_path)
    else:
        raise ConversionError("PDF layout mode must be 'preserve' or 'editable'.")
