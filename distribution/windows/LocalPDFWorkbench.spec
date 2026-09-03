# -*- mode: python ; coding: utf-8 -*-
from __future__ import annotations

import importlib.util
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPEC).resolve().parents[2]
FRONTEND = ROOT / "frontend"
ICON = FRONTEND / "assets" / "images" / "app.ico"

hiddenimports = collect_submodules("uvicorn") + collect_submodules("backend")
datas = [(str(FRONTEND), "frontend")]
if importlib.util.find_spec("imageio_ffmpeg") is not None:
    datas += collect_data_files("imageio_ffmpeg", includes=["binaries/*"])
INDONESIAN_OCR = ROOT / "data" / "ind.traineddata"
if INDONESIAN_OCR.exists():
    datas.append((str(INDONESIAN_OCR), "data"))
binaries = []

# PyInstaller's package hooks collect the native libraries and data used by the
# imports it discovers. Avoid collecting every package submodule here: doing so
# bundled test suites, demos, and unused optional stacks such as Pandas/PyArrow,
# which inflated both the portable folder and Windows cold-start scanning.

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
    excludes=["pytest", "pandas", "pyarrow"],
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
    uac_admin=False,
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
