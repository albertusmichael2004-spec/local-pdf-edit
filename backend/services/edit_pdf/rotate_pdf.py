from __future__ import annotations

from pathlib import Path

from pypdf import PdfWriter

from backend.core.errors import EditingError, PDFReadError
from backend.core.progress import report_fraction, report_progress
from backend.services.shared.pdf_reader import open_pdf_reader


def rotate_pages(input_path: Path, output_path: Path, pages_zero_based: set[int], angle: int) -> int:
    return rotate_pages_with_plan(
        input_path,
        output_path,
        {page: angle for page in pages_zero_based},
    )


def rotate_pages_with_plan(
    input_path: Path,
    output_path: Path,
    rotations_zero_based: dict[int, int],
) -> int:
    normalized = {
        int(page): int(angle) % 360
        for page, angle in rotations_zero_based.items()
        if int(angle) % 360
    }
    if any(angle not in {90, 180, 270} for angle in normalized.values()):
        raise EditingError("Each rotation must be 90, 180, or 270 degrees.")
    if not normalized:
        raise EditingError("Rotate at least one page before exporting.")
    try:
        reader = open_pdf_reader(input_path, "Encrypted PDF. Unlock it before editing.")
        writer = PdfWriter()
        try:
            total = len(reader.pages)
            if any(index < 0 or index >= total for index in normalized):
                raise EditingError(f"Rotation plan contains a page outside 1-{total}.")
            for index, page in enumerate(reader.pages):
                angle = normalized.get(index)
                if angle:
                    page.rotate(angle)
                writer.add_page(page)
                report_fraction("Rotating PDF pages", index + 1, total, 24, 84)
            report_progress("Writing rotated PDF", percent=90)
            with output_path.open("wb") as handle:
                writer.write(handle)
            return len(reader.pages)
        finally:
            writer.close()
    except PDFReadError:
        raise
    except Exception as exc:
        raise EditingError(f"Rotate PDF failed: {exc}") from exc
