from __future__ import annotations

from pathlib import Path

import fitz

from backend.core.errors import EditingError


def crop_pages(
    input_path: Path,
    output_path: Path,
    left_mm: float,
    top_mm: float,
    right_mm: float,
    bottom_mm: float,
    pages_zero_based: set[int] | None,
) -> int:
    mm_to_pt = 72.0 / 25.4
    left, top, right, bottom = [
        max(0.0, value) * mm_to_pt
        for value in (left_mm, top_mm, right_mm, bottom_mm)
    ]
    try:
        with fitz.open(input_path) as doc:
            if doc.needs_pass:
                raise EditingError("Encrypted PDF. Unlock it before editing.")
            for index, page in enumerate(doc):
                if pages_zero_based is not None and index not in pages_zero_based:
                    continue
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
            doc.save(output_path, garbage=4, deflate=True)
            return doc.page_count
    except EditingError:
        raise
    except Exception as exc:
        raise EditingError(f"Crop PDF failed: {exc}") from exc
