from __future__ import annotations

from pathlib import Path

from pypdf import PdfWriter

from backend.core.errors import EditingError, PDFReadError
from backend.services.shared.pdf_reader import open_pdf_reader


def extract_pages(input_path: Path, output_path: Path, pages_zero_based: list[int]) -> int:
    try:
        reader = open_pdf_reader(input_path, "Encrypted PDF. Unlock it before editing.")
        writer = PdfWriter()
        try:
            for index in pages_zero_based:
                writer.add_page(reader.pages[index])
            with output_path.open("wb") as handle:
                writer.write(handle)
            return len(pages_zero_based)
        finally:
            writer.close()
    except PDFReadError:
        raise
    except Exception as exc:
        raise EditingError(f"Extract pages failed: {exc}") from exc
