from __future__ import annotations

from pathlib import Path
from typing import Any

import fitz

from backend.core.errors import EditingError
from backend.services.edit_pdf.extract_pages import extract_pages


def organize_pages(input_path: Path, output_path: Path, page_order_zero_based: list[int]) -> int:
    """Rebuild a PDF in the exact requested page order."""
    return extract_pages(input_path, output_path, page_order_zero_based)


def organize_with_plan(input_path: Path, output_path: Path, plan: list[dict[str, Any]]) -> int:
    """Rebuild a PDF from an editor plan.

    Each plan entry is either an existing source page or a new blank page::

        {"source_page": 3, "rotation": 90}
        {"source_page": null, "width_pt": 595, "height_pt": 842}

    ``source_page`` is one-based to keep the HTTP/UI contract human-readable.
    Rotation is an additional clockwise rotation applied to the inserted page.
    """
    if not plan:
        raise EditingError("The organized PDF must contain at least one page.")

    try:
        with fitz.open(input_path) as source:
            if source.needs_pass:
                raise EditingError("Encrypted PDF. Unlock it before organizing pages.")
            result = fitz.open()
            try:
                for position, entry in enumerate(plan, start=1):
                    source_page = entry.get("source_page")
                    rotation = int(entry.get("rotation", 0) or 0) % 360
                    if rotation not in {0, 90, 180, 270}:
                        raise EditingError(
                            f"Page {position}: rotation must be 0, 90, 180, or 270 degrees."
                        )

                    if source_page is None:
                        width = float(entry.get("width_pt") or 595.0)
                        height = float(entry.get("height_pt") or 842.0)
                        if width < 20 or height < 20:
                            raise EditingError(f"Page {position}: invalid blank-page dimensions.")
                        page = result.new_page(width=width, height=height)
                        if rotation:
                            page.set_rotation(rotation)
                        continue

                    page_number = int(source_page)
                    if page_number < 1 or page_number > source.page_count:
                        raise EditingError(
                            f"Page {position}: source page {page_number} is outside 1-{source.page_count}."
                        )
                    result.insert_pdf(source, from_page=page_number - 1, to_page=page_number - 1)
                    inserted = result[result.page_count - 1]
                    if rotation:
                        inserted.set_rotation((inserted.rotation + rotation) % 360)

                result.save(output_path, garbage=4, deflate=True)
                return result.page_count
            finally:
                result.close()
    except EditingError:
        raise
    except Exception as exc:
        raise EditingError(f"Organize PDF failed: {exc}") from exc
