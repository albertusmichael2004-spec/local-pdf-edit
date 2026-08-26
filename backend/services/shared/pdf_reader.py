from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from backend.core.errors import PDFReadError


def open_pdf_reader(path: Path, encrypted_message: str = "Encrypted PDF. Unlock it first.") -> PdfReader:
    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            raise PDFReadError(encrypted_message)
        return reader
    except PDFReadError:
        raise
    except Exception as exc:
        raise PDFReadError(f"Unable to read PDF: {exc}") from exc


def get_pdf_page_count(path: Path) -> int:
    return len(open_pdf_reader(path).pages)
