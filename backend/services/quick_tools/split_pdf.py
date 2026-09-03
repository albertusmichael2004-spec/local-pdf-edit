from __future__ import annotations

from io import BytesIO
from pathlib import Path
import zipfile

from pypdf import PdfReader, PdfWriter

from backend.core.errors import PDFOperationError, PDFReadError
from backend.core.progress import report_fraction, report_progress
from backend.services.shared.pdf_reader import open_pdf_reader
from backend.utils.page_ranges import PageGroup


def write_selected_pages(
    input_path: Path,
    pages_zero_based: list[int] | tuple[int, ...],
    output: Path,
) -> int:
    reader = open_pdf_reader(input_path)
    writer = PdfWriter()
    try:
        total = len(pages_zero_based)
        for position, page_index in enumerate(pages_zero_based, start=1):
            if page_index < 0 or page_index >= len(reader.pages):
                raise PDFOperationError(f"Page index {page_index + 1} is outside the PDF.")
            writer.add_page(reader.pages[page_index])
            report_fraction("Collecting selected pages", position, total, 24, 82)
        report_progress("Writing extracted PDF", percent=90)
        with output.open("wb") as handle:
            writer.write(handle)
        return len(pages_zero_based)
    except (PDFOperationError, PDFReadError):
        raise
    except Exception as exc:
        raise PDFOperationError(f"Unable to write selected pages: {exc}") from exc
    finally:
        writer.close()


def write_groups_as_one_pdf(input_path: Path, groups: list[PageGroup], output: Path) -> int:
    pages: list[int] = []
    for group in groups:
        pages.extend(group.pages_zero_based)
    return write_selected_pages(input_path, pages, output)


def split_pdf_to_zip(
    input_path: Path,
    groups: list[PageGroup],
    output_zip: Path,
    base_name: str,
) -> int:
    reader = open_pdf_reader(input_path)
    try:
        with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for index, group in enumerate(groups, start=1):
                writer = PdfWriter()
                try:
                    for page_index in group.pages_zero_based:
                        writer.add_page(reader.pages[page_index])
                    label = group.label.replace(",", "-")
                    piece_name = f"{base_name}_part_{index:02d}_pages_{label}.pdf"
                    piece_path = output_zip.parent / piece_name
                    with piece_path.open("wb") as handle:
                        writer.write(handle)
                    archive.write(piece_path, arcname=piece_path.name)
                    piece_path.unlink(missing_ok=True)
                    report_fraction("Building split archive", index, len(groups), 24, 92)
                finally:
                    writer.close()
        return len(groups)
    except (PDFOperationError, PDFReadError):
        raise
    except Exception as exc:
        raise PDFOperationError(f"Split failed: {exc}") from exc


def _serialized_size(reader: PdfReader, page_indexes: list[int]) -> int:
    writer = PdfWriter()
    try:
        for index in page_indexes:
            writer.add_page(reader.pages[index])
        buffer = BytesIO()
        writer.write(buffer)
        return buffer.tell()
    finally:
        writer.close()


def groups_by_approx_size(input_path: Path, max_bytes: int) -> tuple[list[PageGroup], list[int]]:
    """Greedily group pages so each generated PDF aims to stay <= max_bytes."""
    if max_bytes < 50 * 1024:
        raise PDFOperationError("Split-by-size target must be at least 0.05 MB.")

    reader = open_pdf_reader(input_path)
    total_pages = len(reader.pages)
    groups: list[PageGroup] = []
    oversized_parts: list[int] = []
    current: list[int] = []

    for page_index in range(total_pages):
        tentative = current + [page_index]
        tentative_size = _serialized_size(reader, tentative)
        if current and tentative_size > max_bytes:
            groups.append(PageGroup(
                label=_label(current),
                pages_zero_based=tuple(current),
            ))
            current = [page_index]
            if _serialized_size(reader, current) > max_bytes:
                oversized_parts.append(len(groups) + 1)
        else:
            current = tentative
            if len(current) == 1 and tentative_size > max_bytes:
                oversized_parts.append(len(groups) + 1)
        report_fraction("Estimating split sizes", page_index + 1, total_pages, 22, 70)

    if current:
        groups.append(PageGroup(
            label=_label(current),
            pages_zero_based=tuple(current),
        ))
    return groups, sorted(set(oversized_parts))


def _label(page_indexes: list[int]) -> str:
    if not page_indexes:
        return ""
    one_based = [index + 1 for index in page_indexes]
    if len(one_based) == 1:
        return str(one_based[0])
    return f"{one_based[0]}-{one_based[-1]}"
