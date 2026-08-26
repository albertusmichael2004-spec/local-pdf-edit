from __future__ import annotations

import os
from pathlib import Path
import re
import shutil


def _from_environment(variable: str) -> str | None:
    value = os.getenv(variable)
    return value if value and Path(value).exists() else None


def _from_path(names: tuple[str, ...]) -> str | None:
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def find_ghostscript() -> str | None:
    explicit = _from_environment("GHOSTSCRIPT_PATH")
    if explicit:
        return explicit
    discovered = _from_path(("gswin64c", "gswin32c", "gs"))
    if discovered:
        return discovered
    if os.name != "nt":
        return None

    roots = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "gs",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "gs",
    ]
    candidates: list[Path] = []
    for root in roots:
        if root.exists():
            candidates.extend(root.glob("gs*/bin/gswin64c.exe"))
            candidates.extend(root.glob("gs*/bin/gswin32c.exe"))
    if not candidates:
        return None

    def version_key(candidate: Path) -> tuple[int, ...]:
        numbers = re.findall(r"\d+", candidate.parent.parent.name)
        return tuple(int(number) for number in numbers) or (0,)

    return str(sorted(candidates, key=version_key, reverse=True)[0])


def find_libreoffice() -> str | None:
    explicit = _from_environment("LIBREOFFICE_PATH")
    if explicit:
        return explicit
    discovered = _from_path(("soffice", "libreoffice"))
    if discovered:
        return discovered
    if os.name != "nt":
        return None

    for root in (
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
    ):
        candidate = root / "LibreOffice" / "program" / "soffice.exe"
        if candidate.exists():
            return str(candidate)
    return None


def find_tesseract() -> str | None:
    explicit = _from_environment("TESSERACT_PATH")
    if explicit:
        return explicit
    discovered = _from_path(("tesseract", "tesseract.exe"))
    if discovered:
        return discovered
    if os.name != "nt":
        return None

    candidates = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Tesseract-OCR" / "tesseract.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Tesseract-OCR" / "tesseract.exe",
    ]
    return next((str(path) for path in candidates if path.exists()), None)
