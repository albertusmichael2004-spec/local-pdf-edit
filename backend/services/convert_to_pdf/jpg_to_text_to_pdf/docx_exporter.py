from __future__ import annotations

from pathlib import Path

from backend.core.errors import ConversionError
from backend.services.shared.ocr.models import OCRPage

from .text_layout import page_lines


def export_docx(
    pages: list[OCRPage],
    output_path: Path,
) -> None:
    """
    Export OCR results as an editable Word document.

    Text order follows OCR line coordinates.
    Complex layouts such as tables, multi-column pages,
    graphics, and text boxes may not be reconstructed exactly.
    """

    try:
        from docx import Document
        from docx.shared import Pt

    except ImportError as exc:
        raise ConversionError(
            "python-docx is required for Word export. "
            "Run pip install -r requirements.txt."
        ) from exc

    document = Document()

    normal_style = document.styles["Normal"]
    normal_style.font.name = "Arial"
    normal_style.font.size = Pt(10.5)

    for page_index, page in enumerate(pages):
        lines = page_lines(page)
        if not lines:
            lines = ["(No text detected on this image.)"]
        for line in lines:
            paragraph = document.add_paragraph(line)
            paragraph.paragraph_format.space_before = Pt(0)
            paragraph.paragraph_format.space_after = Pt(0)
            paragraph.paragraph_format.line_spacing = 1
        if page_index < len(pages) - 1:
            document.add_page_break()

    try:
        document.save(
            output_path
        )

    except Exception as exc:
        raise ConversionError(
            f"Failed to create Word document: {exc}"
        ) from exc
