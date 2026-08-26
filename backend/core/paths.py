from __future__ import annotations

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
    build it lives beside LocalPDFWorkbench.exe, not inside the temporary
    _MEIPASS extraction directory.
    """
    if getattr(sys, "frozen", False):
        root = Path(sys.executable).resolve().parent / "data"
    else:
        root = PROJECT_ROOT / "data"
    root.mkdir(parents=True, exist_ok=True)
    return root


def custom_font_dir() -> Path:
    path = persistent_data_root() / "fonts"
    path.mkdir(parents=True, exist_ok=True)
    return path
