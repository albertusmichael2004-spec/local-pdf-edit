from __future__ import annotations

from pathlib import Path

from backend.core.paths import persistent_data_root, runtime_root


def resolve_ocr_language(requested: str, data_root: Path | None = None) -> tuple[str, Path | None]:
    """Resolve an OCR language without breaking machines that only have English."""
    roots = [data_root] if data_root else [persistent_data_root(), runtime_root() / "data"]
    normalized = requested.strip().lower()
    choices = [part for part in normalized.split("+") if part and part != "auto"]
    if not choices:
        choices = ["ind", "eng"]
    for language in choices:
        for root in roots:
            if root and (root / f"{language}.traineddata").is_file():
                return language, root
    return choices[-1], None
