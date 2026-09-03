from __future__ import annotations

from pathlib import Path

import fitz
from PIL import Image

from backend.core.errors import OCRError
from backend.core.executables import find_tesseract
from backend.core.progress import report_fraction, report_progress
from backend.services.shared.tesseract import image_to_searchable_pdf

def ocr_pdf(input_path: Path, output_path: Path, language: str = "eng", dpi: int = 200) -> int:
    tesseract = find_tesseract()
    if not tesseract:
        raise OCRError(
            "Tesseract was not found. Install Tesseract OCR and restart the app, "
            "or set TESSERACT_PATH to the executable."
        )
   
    result = fitz.open()
    try:
        with fitz.open(input_path) as source:
            if source.needs_pass:
                raise OCRError("Encrypted PDF. Unlock it before OCR.")
            scale = dpi / 72.0
            report_progress("Preparing OCR engine", percent=22, detail=f"{source.page_count} page(s)")
            for index, page in enumerate(source, start=1):
                pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                try:
                    pdf_bytes = image_to_searchable_pdf(
                        image=image, 
                        tesseract_executable=tesseract, 
                        language=language,
                    )
                finally:
                    image.close()
                with fitz.open(stream=pdf_bytes, filetype="pdf") as page_pdf:
                    result.insert_pdf(page_pdf)
                report_fraction("Recognizing PDF pages", index, source.page_count, 24, 90)
        report_progress("Saving searchable PDF", percent=94)
        result.save(output_path, garbage=4, deflate=True)
        return result.page_count
    except OCRError:
        raise
    except Exception as exc:
        raise OCRError(f"OCR failed: {exc}") from exc
    finally:
        result.close()
