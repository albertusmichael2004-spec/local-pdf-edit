from __future__ import annotations

from io import BytesIO
from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:
    import fitz

from PIL import Image, ImageOps

from backend.core.errors import ConversionError

from .models import OCRPage


DEFAULT_PAGE_WIDTH = 595.0


def render_searchable_pdf(
    pages: list[OCRPage],
    output_path: Path,
) -> None:
    document = fitz.open()

    try:
        for result in pages:
            aspect_ratio = (
                result.source_height
                / result.source_width
            )

            page_width = (
                DEFAULT_PAGE_WIDTH
            )

            page_height = (
                page_width
                * aspect_ratio
            )

            page = document.new_page(
                width=page_width,
                height=page_height,
            )

            # Prefer direct embedding for formats supported
            # natively by PyMuPDF. Fall back to an in-memory
            # PNG for formats such as WEBP.
            try:
                page.insert_image(
                    page.rect,
                    filename=str(result.source_path),
                    keep_proportion=False,
                )
            except Exception as direct_error:
                try:
                    with Image.open(result.source_path) as source:
                        normalized = (
                            ImageOps
                            .exif_transpose(source)
                            .convert("RGB")
                        )

                        buffer = BytesIO()

                        normalized.save(
                            buffer,
                            format="PNG",
                        )

                    page.insert_image(
                        page.rect,
                        stream=buffer.getvalue(),
                        keep_proportion=False,
                    )

                except Exception as fallback_error:
                    raise ConversionError(
                        f"Could not embed "
                        f"{result.source_path.name} "
                        f"in the searchable PDF: "
                        f"{fallback_error}"
                    ) from direct_error

            scale_x = (
                page_width
                / result.ocr_width
            )

            scale_y = (
                page_height
                / result.ocr_height
            )

            for word in result.words:
                x = (
                    word.left
                    * scale_x
                )

                y = (
                    word.top
                    * scale_y
                )

                height = (
                    word.height
                    * scale_y
                )

                font_size = max(
                    4,
                    height * 0.80,
                )

                baseline = (
                    y
                    + height
                    - font_size * 0.12
                )

                # render_mode=3 =
                # invisible text.
                page.insert_text(
                    (
                        x,
                        baseline,
                    ),
                    word.text,
                    fontsize=font_size,
                    fontname="helv",
                    render_mode=3,
                    overlay=True,
                )

        document.save(
            output_path,
            garbage=4,
            deflate=True,
        )

    finally:
        document.close()