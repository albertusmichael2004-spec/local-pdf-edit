# -*- mode: python ; coding: utf-8 -*-
from __future__ import annotations

import importlib.util
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

ROOT = Path(SPEC).resolve().parents[2]
FRONTEND = ROOT / "frontend"
ICON = FRONTEND / "assets" / "images" / "app.ico"

hiddenimports: list[str] = []
datas = [(str(FRONTEND), "frontend")]
INDONESIAN_OCR = ROOT / "data" / "ind.traineddata"
if INDONESIAN_OCR.exists():
    datas.append((str(INDONESIAN_OCR), "data"))
binaries = []

# Explicit collection keeps the portable Windows build robust for packages that
# load plugins/data/native DLLs dynamically. This is intentionally build-only;
# source mode does not depend on PyInstaller.
for package in [
    "uvicorn",
    "fastapi",
    "starlette",
    "multipart",
    "cryptography",
    "pdf2docx",
    "fitz",
    "pypdf",
    "webview",
    "pptx",
    "docx",
    "openpyxl",
    "pdfplumber",
    "pytesseract",
    "weasyprint",
    "reportlab",
    "bs4",
    "PIL",
]:
    try:
        hiddenimports += collect_submodules(package)
        datas += collect_data_files(package)
        binaries += collect_dynamic_libs(package)
    except Exception:
        pass

if importlib.util.find_spec("clr") is not None:
    hiddenimports.append("clr")

analysis = Analysis(
    [str(ROOT / "desktop.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest"],
    noarchive=False,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="LocalPDFWorkbench",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    icon=str(ICON),
)

coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    name="LocalPDFWorkbench",
)
