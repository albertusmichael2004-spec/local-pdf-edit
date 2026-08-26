from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path

import fitz

from backend.core.errors import PreviewError


@dataclass(frozen=True)
class PagePreview:
    page: int
    image: str
    width_pt: float
    height_pt: float
    rotation: int


def render_page_preview(path: Path, page_number: int, max_width: int = 440) -> PagePreview:
    try:
        with fitz.open(path) as doc:
            if doc.needs_pass:
                raise PreviewError("Encrypted PDF. Unlock it before previewing.")
            if page_number < 1 or page_number > doc.page_count:
                raise PreviewError(f"Page {page_number} is outside 1-{doc.page_count}.")
            page = doc[page_number - 1]
            rect = page.rect
            scale = min(2.0, max(0.45, max_width / max(1.0, rect.width)))
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            payload = base64.b64encode(pix.tobytes("jpeg", jpg_quality=76)).decode("ascii")
            return PagePreview(
                page=page_number,
                image=f"data:image/jpeg;base64,{payload}",
                width_pt=float(rect.width),
                height_pt=float(rect.height),
                rotation=int(page.rotation or 0),
            )
    except PreviewError:
        raise
    except Exception as exc:
        raise PreviewError(f"Unable to render PDF preview: {exc}") from exc


def render_page_data_url(path: Path, page_number: int, max_width: int = 440) -> str:
    """Backward-compatible helper for callers that only need the image."""
    return render_page_preview(path, page_number, max_width=max_width).image
