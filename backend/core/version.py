from __future__ import annotations

from pathlib import Path
import sys


def version_file() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / "VERSION"
    return Path(__file__).resolve().parents[2] / "VERSION"


def read_app_version() -> str:
    try:
        value = version_file().read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0.0"
    parts = value.split(".")
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        return value
    return "0.0.0"


APP_VERSION = read_app_version()
