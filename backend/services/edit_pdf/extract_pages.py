from __future__ import annotations

from pathlib import Path

from pypdf import PdfWriter

from backend.core.errors import EditingError, PDFReadError
from backend.core.progress import report_fraction, report_progress
from backend.services.shared.pdf_reader import open_pdf_reader


def extract_pages(input_path: Path, output_path: Path, pages_zero_based: list[int]) -> int:
    try:
        reader = open_pdf_reader(input_path, "Encrypted PDF. Unlock it before editing.")
        writer = PdfWriter()
        try:
            total = len(pages_zero_based)
            for position, index in enumerate(pages_zero_based, start=1):
                writer.add_page(reader.pages[index])
                report_fraction("Extracting selected pages", position, total, 24, 84)
            report_progress("Writing extracted PDF", percent=90)
            with output_path.open("wb") as handle:
                writer.write(handle)
            return len(pages_zero_based)
        finally:
            writer.close()
    except PDFReadError:
        raise
    except Exception as exc:
        raise EditingError(f"Extract pages failed: {exc}") from exc
