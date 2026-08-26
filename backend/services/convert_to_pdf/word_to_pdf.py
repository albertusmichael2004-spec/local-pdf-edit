from __future__ import annotations

from pathlib import Path

from backend.core.executables import find_libreoffice
from backend.services.shared.office import office_to_pdf
from backend.services.shared.renderers.docx_renderer import render_docx_to_pdf


def word_to_pdf(input_path: Path, output_path: Path) -> str:
    if find_libreoffice():
        try:
            return office_to_pdf(input_path, output_path)
        except Exception:
            if input_path.suffix.lower() != ".docx":
                raise
    return render_docx_to_pdf(input_path, output_path)
