from __future__ import annotations

import tempfile
from pathlib import Path

from backend.services.shared.ocr.models import OCRPage
from backend.services.shared.ocr.tesseract_layout import (
    recognize_best_page,
)


def recognize_images(
    image_paths: list[Path],
    tesseract_executable: str,
    language: str,
    quality: str,
) -> list[OCRPage]:
    """
    Run OCR for all uploaded images in their current order.

    Each image becomes one OCRPage object containing:
    - detected words
    - coordinates
    - confidence
    - original page dimensions
    - OCR processing dimensions
    """

    results: list[OCRPage] = []

    with tempfile.TemporaryDirectory(
        prefix="pdfwb-image-ocr-"
    ) as temp_dir:
        temp_root = Path(temp_dir)

        for index, image_path in enumerate(
            image_paths,
            start=1,
        ):
            page_workspace = (
                temp_root
                / f"page_{index:04d}"
            )

            result = recognize_best_page(
                source_path=image_path,
                workspace=page_workspace,
                tesseract_executable=tesseract_executable,
                language=language,
                quality=quality,
            )

            results.append(result)

    return results