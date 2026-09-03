from __future__ import annotations

from pathlib import Path

from pypdf import PdfWriter

from backend.core.errors import EditingError, PDFReadError
from backend.core.progress import report_fraction, report_progress
from backend.services.shared.pdf_reader import open_pdf_reader


def remove_pages(input_path: Path, output_path: Path, remove_zero_based: set[int]) -> int:
    try:
        reader = open_pdf_reader(input_path, "Encrypted PDF. Unlock it before editing.")
        writer = PdfWriter()
        try:
            kept = 0
            total = len(reader.pages)
            for index, page in enumerate(reader.pages):
                if index not in remove_zero_based:
                    writer.add_page(page)
                    kept += 1
                report_fraction("Filtering PDF pages", index + 1, total, 24, 84)
            if kept == 0:
                raise EditingError("Removing those pages would create an empty PDF.")
            report_progress("Writing updated PDF", percent=90)
            with output_path.open("wb") as handle:
                writer.write(handle)
            return kept
        finally:
            writer.close()
    except (EditingError, PDFReadError):
        raise
    except Exception as exc:
        raise EditingError(f"Remove pages failed: {exc}") from exc
