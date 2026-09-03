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


def _find_windows_app(variable: str, names: tuple[str, ...], candidates: tuple[Path, ...]) -> str | None:
    explicit = _from_environment(variable)
    if explicit:
        return explicit
    discovered = _from_path(names)
    if discovered:
        return discovered
    return next((str(path) for path in candidates if path.exists()), None)


def _bundled_ffmpeg() -> str | None:
    """Return imageio-ffmpeg's redistributable binary when it is bundled."""
    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        executable = Path(get_ffmpeg_exe())
        return str(executable) if executable.is_file() else None
    except Exception:
        return None


def find_ffmpeg() -> str | None:
    root = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    discovered = _find_windows_app(
        "FFMPEG_PATH",
        ("ffmpeg", "ffmpeg.exe"),
        tuple(root.glob("ffmpeg*/bin/ffmpeg.exe")),
    )
    return discovered or _bundled_ffmpeg()


def find_ffprobe() -> str | None:
    explicit = _from_environment("FFPROBE_PATH")
    if explicit:
        return explicit
    discovered = _from_path(("ffprobe", "ffprobe.exe"))
    if discovered:
        return discovered
    ffmpeg = find_ffmpeg()
    sibling = Path(ffmpeg).with_name("ffprobe.exe") if ffmpeg else None
    return str(sibling) if sibling and sibling.is_file() else None


def find_ebook_convert() -> str | None:
    roots = (
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
    )
    candidates = tuple(root / "Calibre2" / "ebook-convert.exe" for root in roots)
    return _find_windows_app("EBOOK_CONVERT_PATH", ("ebook-convert", "ebook-convert.exe"), candidates)
