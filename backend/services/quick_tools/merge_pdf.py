from __future__ import annotations

from pathlib import Path

from pypdf import PdfWriter

from backend.core.errors import PDFOperationError, PDFReadError
from backend.services.shared.pdf_reader import open_pdf_reader


def merge_pdfs(inputs: list[Path], output: Path) -> int:
    if len(inputs) < 2:
        raise PDFOperationError("Upload at least two PDFs to merge.")
    writer = PdfWriter()
    total_pages = 0
    try:
        for input_path in inputs:
            reader = open_pdf_reader(
                input_path,
                "Encrypted PDFs are not supported unless decrypted first.",
            )
            writer.append(reader)
            total_pages += len(reader.pages)
        with output.open("wb") as handle:
            writer.write(handle)
        return total_pages
    except (PDFOperationError, PDFReadError):
        raise
    except Exception as exc:
        raise PDFOperationError(f"Merge failed: {exc}") from exc
    finally:
        writer.close()
