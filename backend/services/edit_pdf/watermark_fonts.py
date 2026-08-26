from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re

from backend.core.paths import custom_font_dir


@dataclass(frozen=True)
class WatermarkFont:
    key: str
    label: str
    builtin_name: str | None = None
    file_path: Path | None = None


# Built-in PDF fonts are always available. Windows font filenames are resolved
# opportunistically so the same UI can expose familiar desktop fonts without
# bundling or redistributing font files.
_FONT_SPECS: dict[str, tuple[str, str | None, tuple[str, ...]]] = {
    "arial": ("Arial", "helv", ("arial.ttf", "arialbd.ttf")),
    "calibri": ("Calibri", "helv", ("calibri.ttf",)),
    "times-new-roman": ("Times New Roman", "Times-Roman", ("times.ttf", "timesnewroman.ttf")),
    "segoe-ui": ("Segoe UI", "helv", ("segoeui.ttf",)),
    "georgia": ("Georgia", "Times-Roman", ("georgia.ttf",)),
    "verdana": ("Verdana", "helv", ("verdana.ttf",)),
    "trebuchet-ms": ("Trebuchet MS", "helv", ("trebuc.ttf",)),
    "courier-new": ("Courier New", "cour", ("cour.ttf",)),
    "montserrat": ("Montserrat", "helv", ("Montserrat-Regular.ttf", "montserrat-regular.ttf")),
    "helvetica": ("Helvetica", "helv", ()),
}


def _windows_font_roots() -> list[Path]:
    roots: list[Path] = []
    windir = os.getenv("WINDIR")
    if windir:
        roots.append(Path(windir) / "Fonts")
    local = os.getenv("LOCALAPPDATA")
    if local:
        roots.append(Path(local) / "Microsoft" / "Windows" / "Fonts")
    return roots


def _find_installed_font(candidates: tuple[str, ...]) -> Path | None:
    if not candidates:
        return None
    lowered = {candidate.lower() for candidate in candidates}
    for root in _windows_font_roots():
        if not root.exists():
            continue
        for candidate in candidates:
            direct = root / candidate
            if direct.exists():
                return direct
        # Some installations use slightly different Montserrat/Times filenames.
        for path in root.glob("*.*tf"):
            if path.name.lower() in lowered:
                return path
    return None


def builtin_fonts() -> list[dict[str, str | bool]]:
    result: list[dict[str, str | bool]] = []
    for key, (label, _fallback, candidates) in _FONT_SPECS.items():
        installed = _find_installed_font(candidates)
        result.append({"key": key, "label": label, "installed": bool(installed) or not candidates})
    return result


def custom_fonts() -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for path in sorted(custom_font_dir().glob("*")):
        if path.suffix.lower() not in {".ttf", ".otf"}:
            continue
        result.append({"key": f"custom:{path.name}", "label": path.stem})
    return result


def resolve_font(key: str) -> WatermarkFont:
    key = (key or "arial").strip()
    if key.startswith("custom:"):
        filename = Path(key.split(":", 1)[1]).name
        path = custom_font_dir() / filename
        if not path.exists() or path.suffix.lower() not in {".ttf", ".otf"}:
            raise ValueError("The selected custom font is no longer available.")
        return WatermarkFont(key=key, label=path.stem, file_path=path)

    if key not in _FONT_SPECS:
        key = "arial"
    label, fallback, candidates = _FONT_SPECS[key]
    installed = _find_installed_font(candidates)
    return WatermarkFont(
        key=key,
        label=label,
        builtin_name=None if installed else fallback,
        file_path=installed,
    )


def safe_font_filename(filename: str) -> str:
    name = Path(filename or "font.ttf").name
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).stem).strip("._") or "font"
    suffix = Path(name).suffix.lower()
    if suffix not in {".ttf", ".otf"}:
        raise ValueError("Custom watermark fonts must be .ttf or .otf files.")
    return f"{stem}{suffix}"
