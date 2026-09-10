# -*- mode: python ; coding: utf-8 -*-
from __future__ import annotations

import importlib.util
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

ROOT = Path(SPEC).resolve().parents[2]
FRONTEND = ROOT / "frontend"
ICON = FRONTEND / "assets" / "images" / "app.ico"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
version_parts = tuple(int(part) for part in VERSION.split("."))
if not 1 <= len(version_parts) <= 4:
    raise ValueError(f"VERSION must contain 1 to 4 numeric components: {VERSION!r}")
version_tuple = version_parts + (0,) * (4 - len(version_parts))

version_info = VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=version_tuple,
        prodvers=version_tuple,
        mask=0x3F,
        flags=0x0,
        OS=0x40004,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "040904B0",
                    [
                        StringStruct("CompanyName", "Albertus Michael"),
                        StringStruct("FileDescription", "Local PDF Workbench"),
                        StringStruct("FileVersion", VERSION),
                        StringStruct("InternalName", "LocalPDFWorkbench"),
                        StringStruct("LegalCopyright", "Copyright (C) 2026 Albertus Michael"),
                        StringStruct("OriginalFilename", "LocalPDFWorkbench.exe"),
                        StringStruct("ProductName", "Local PDF Workbench"),
                        StringStruct("ProductVersion", VERSION),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)

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
    version=version_info,
)

coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    name="LocalPDFWorkbench",
)
