from __future__ import annotations

from pathlib import Path

from pypdf import PdfWriter

from backend.core.errors import EditingError, PDFReadError
from backend.services.shared.pdf_reader import open_pdf_reader


def rotate_pages(input_path: Path, output_path: Path, pages_zero_based: set[int], angle: int) -> int:
    if angle not in {90, 180, 270}:
        raise EditingError("Rotation must be 90, 180, or 270 degrees.")
    try:
        reader = open_pdf_reader(input_path, "Encrypted PDF. Unlock it before editing.")
        writer = PdfWriter()
        try:
            for index, page in enumerate(reader.pages):
                if index in pages_zero_based:
                    page.rotate(angle)
                writer.add_page(page)
            with output_path.open("wb") as handle:
                writer.write(handle)
            return len(reader.pages)
        finally:
            writer.close()
    except PDFReadError:
        raise
    except Exception as exc:
        raise EditingError(f"Rotate PDF failed: {exc}") from exc
