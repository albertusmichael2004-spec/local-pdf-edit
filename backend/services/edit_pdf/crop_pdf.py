from __future__ import annotations

from pathlib import Path

import fitz

from backend.core.errors import EditingError
from backend.core.progress import report_fraction, report_progress


def crop_pages(
    input_path: Path,
    output_path: Path,
    left_mm: float,
    top_mm: float,
    right_mm: float,
    bottom_mm: float,
    pages_zero_based: set[int] | None,
) -> int:
    indexes = pages_zero_based
    with fitz.open(input_path) as source:
        page_count = source.page_count
    selected = range(page_count) if indexes is None else indexes
    plan = {
        int(index): (left_mm, top_mm, right_mm, bottom_mm)
        for index in selected
    }
    return crop_pages_with_plan(input_path, output_path, plan)


def crop_pages_with_plan(
    input_path: Path,
    output_path: Path,
    crop_plan_zero_based: dict[int, tuple[float, float, float, float]],
) -> int:
    mm_to_pt = 72.0 / 25.4
    try:
        with fitz.open(input_path) as doc:
            if doc.needs_pass:
                raise EditingError("Encrypted PDF. Unlock it before editing.")
            if not crop_plan_zero_based:
                raise EditingError("Apply a crop to at least one page before exporting.")
            if any(index < 0 or index >= doc.page_count for index in crop_plan_zero_based):
                raise EditingError(f"Crop plan contains a page outside 1-{doc.page_count}.")
            for index, page in enumerate(doc):
                margins = crop_plan_zero_based.get(index)
                if margins is None:
                    continue
                left, top, right, bottom = [max(0.0, float(value)) * mm_to_pt for value in margins]
                rect = page.cropbox
                new_rect = fitz.Rect(
                    rect.x0 + left,
                    rect.y0 + top,
                    rect.x1 - right,
                    rect.y1 - bottom,
                )
                if new_rect.width < 20 or new_rect.height < 20:
                    raise EditingError(f"Crop margins are too large for page {index + 1}.")
                page.set_cropbox(new_rect)
                report_fraction("Cropping PDF pages", index + 1, doc.page_count, 24, 86)
            report_progress("Saving cropped PDF", percent=92)
            doc.save(output_path, garbage=4, deflate=True)
            return doc.page_count
    except EditingError:
        raise
    except Exception as exc:
        raise EditingError(f"Crop PDF failed: {exc}") from exc
