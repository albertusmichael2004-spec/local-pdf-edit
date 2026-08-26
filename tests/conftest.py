from __future__ import annotations

from pathlib import Path

import fitz
import pytest


@pytest.fixture
def make_pdf():
    def _make(path: Path, pages: int = 4, prefix: str = "Page") -> Path:
        with fitz.open() as doc:
            for index in range(pages):
                page = doc.new_page(width=400, height=600)
                page.insert_text((50, 80), f"{prefix} {index + 1}", fontsize=20)
            doc.save(path)
        return path
    return _make
