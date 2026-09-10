from __future__ import annotations

import os
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def runtime_root() -> Path:
    """Return the project root in source mode or PyInstaller extraction root."""
    bundle_root = getattr(sys, "_MEIPASS", None)
    return Path(bundle_root) if bundle_root else PROJECT_ROOT


def frontend_root() -> Path:
    return runtime_root() / "frontend"


def app_icon() -> Path:
    return frontend_root() / "assets" / "images" / "app.ico"


def persistent_data_root() -> Path:
    """Writable data directory that survives app restarts.

    In source mode it lives beside the source tree. In a portable PyInstaller
    build it lives in the current user's Local AppData directory so an install
    under Program Files never needs runtime elevation.
    """
    if getattr(sys, "frozen", False):
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            root = Path(local_app_data) / "LocalPDFWorkbench"
        else:
            root = Path.home() / ".local-pdf-workbench"
    else:
        root = PROJECT_ROOT / "data"
    root.mkdir(parents=True, exist_ok=True)
    return root


def custom_font_dir() -> Path:
    path = persistent_data_root() / "fonts"
    path.mkdir(parents=True, exist_ok=True)
    return path
