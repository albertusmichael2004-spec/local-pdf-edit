from __future__ import annotations

import importlib.util
from pathlib import Path
import platform
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.executables import find_ghostscript, find_libreoffice, find_tesseract


def module_status(module: str) -> str:
    return "OK" if importlib.util.find_spec(module) else "MISSING"


def main() -> None:
    print(f"Python: {sys.version.split()[0]} ({platform.system()})")
    print(f"Interpreter: {sys.executable}")
    print()

    modules = [
        "fastapi",
        "uvicorn",
        "pypdf",
        "cryptography",
        "fitz",
        "pdf2docx",
        "docx",
        "PIL",
        "pytesseract",
        "pptx",
        "openpyxl",
        "pdfplumber",
        "weasyprint",
        "reportlab",
        "bs4",
        "webview",
    ]
    for module in modules:
        print(f"{module:14} {module_status(module)}")

    print()
    print(f"Ghostscript    {find_ghostscript() or 'MISSING (Compress PDF unavailable)'}")
    print(f"Tesseract      {find_tesseract() or 'MISSING (OCR PDF unavailable)'}")
    print(
        "LibreOffice    "
        f"{find_libreoffice() or 'OPTIONAL MISSING (modern DOCX/PPTX/XLSX local fallbacks remain available)'}"
    )


if __name__ == "__main__":
    main()
