from __future__ import annotations

from pathlib import Path

import fitz

from backend.core.errors import ConversionError

def pdf_to_docx_text_fallback(input_path: Path, output_path: Path) -> None:
    """Basic text-only DOCX fallback when pdf2docx is unavailable."""
    try:
        from docx import Document
    except ImportError as exc:
        raise ConversionError(
            "Neither pdf2docx nor python-docx is available. Run pip install -r requirements.txt."
        ) from exc
    try:
        document = Document()
        with fitz.open(input_path) as pdf:
            if pdf.needs_pass:
                raise ConversionError("Encrypted PDF. Unlock it before conversion.")
            for page_index, page in enumerate(pdf):
                blocks = page.get_text("blocks")
                for block in sorted(blocks, key=lambda b: (round(b[1], 1), round(b[0], 1))):
                    text = (block[4] or "").strip()
                    if text:
                        document.add_paragraph(text)
                if page_index < pdf.page_count - 1:
                    document.add_page_break()
        document.save(output_path)
    except ConversionError:
        raise
    except Exception as exc:
        raise ConversionError(f"Fallback PDF to Word conversion failed: {exc}") from exc

def pdf_to_docx(input_path: Path, output_path: Path) -> None:
    """Convert a digital PDF to DOCX using pdf2docx when available.

    If pdf2docx cannot be imported, a text-oriented python-docx fallback keeps
    the feature functional, but layout fidelity is intentionally lower.
    """
    try:
        from pdf2docx import Converter
    except ImportError:
        pdf_to_docx_text_fallback(input_path, output_path)
        return

    converter = None
    try:
        converter = Converter(str(input_path))
        converter.convert(str(output_path), start=0, end=None)
    except Exception as exc:
        raise ConversionError(f"PDF to Word conversion failed: {exc}") from exc
    finally:
        if converter is not None:
            converter.close()
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise ConversionError("Conversion completed without producing a DOCX file.")
