from __future__ import annotations

from pathlib import Path
import zipfile

import fitz

from backend.core.errors import ConversionError
from backend.core.progress import report_fraction

def pdf_to_jpg_zip(input_path: Path, output_zip: Path, dpi: int = 180, quality: int = 88) -> int:
    try:
        with fitz.open(input_path) as doc:
            if doc.needs_pass:
                raise ConversionError("Encrypted PDF. Unlock it before conversion.")
            scale = dpi / 72.0
            with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for idx, page in enumerate(doc, start=1):
                    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                    data = pix.tobytes("jpeg", jpg_quality=quality)
                    archive.writestr(f"page_{idx:03d}.jpg", data)
                    report_fraction("Rendering PDF pages to JPG", idx, doc.page_count, 24, 94)
            return doc.page_count
    except ConversionError:
        raise
    except Exception as exc:
        raise ConversionError(f"PDF to JPG conversion failed: {exc}") from exc
