from __future__ import annotations

from pathlib import Path

import fitz
from PIL import Image

from backend.core.errors import ConversionError
from backend.core.progress import report_fraction, report_progress

def jpg_to_pdf(image_paths: list[Path], output_path: Path) -> int:
    """Create a PDF with one page per image using PyMuPDF.

    This avoids Pillow's PDF writer, which can be fragile with some Windows
    image encodings and pywebview upload combinations.
    """
    if not image_paths:
        raise ConversionError("Upload at least one JPG or PNG image.")
    doc = fitz.open()
    try:
        for index, path in enumerate(image_paths, start=1):
            try:
                with Image.open(path) as image:
                    image.verify()
                with Image.open(path) as image:
                    width_px, height_px = image.size
            except Exception as exc:
                raise ConversionError(f"{path.name} is not a readable JPG/PNG image: {exc}") from exc
            # 96 CSS pixels/inch produces a natural physical page size while
            # preserving the original aspect ratio.
            page_w = max(72.0, width_px * 72.0 / 96.0)
            page_h = max(72.0, height_px * 72.0 / 96.0)
            page = doc.new_page(width=page_w, height=page_h)
            page.insert_image(page.rect, filename=str(path), keep_proportion=True)
            report_fraction("Adding images to PDF", index, len(image_paths), 24, 88)
        report_progress("Saving image PDF", percent=94)
        doc.save(output_path, garbage=4, deflate=True)
    except ConversionError:
        raise
    except Exception as exc:
        raise ConversionError(f"Image to PDF conversion failed: {exc}") from exc
    finally:
        doc.close()
    return len(image_paths)
