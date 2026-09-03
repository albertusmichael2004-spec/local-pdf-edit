from __future__ import annotations

from pathlib import Path

from pypdf import PdfWriter

from backend.core.errors import PDFOperationError, PDFReadError
from backend.core.progress import report_fraction, report_progress
from backend.services.shared.pdf_reader import open_pdf_reader


def merge_pdfs(inputs: list[Path], output: Path) -> int:
    if len(inputs) < 2:
        raise PDFOperationError("Upload at least two PDFs to merge.")
    writer = PdfWriter()
    total_pages = 0
    try:
        report_progress("Reading source PDFs", percent=22, detail=f"{len(inputs)} file(s)")
        for index, input_path in enumerate(inputs, start=1):
            reader = open_pdf_reader(
                input_path,
                "Encrypted PDFs are not supported unless decrypted first.",
            )
            writer.append(reader)
            total_pages += len(reader.pages)
            report_fraction("Merging PDF files", index, len(inputs), 24, 86)
        report_progress("Writing merged PDF", percent=92, detail=f"{total_pages} page(s)")
        with output.open("wb") as handle:
            writer.write(handle)
        return total_pages
    except (PDFOperationError, PDFReadError):
        raise
    except Exception as exc:
        raise PDFOperationError(f"Merge failed: {exc}") from exc
    finally:
        writer.close()
