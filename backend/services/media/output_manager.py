from __future__ import annotations

import mimetypes
from pathlib import Path
import zipfile

from backend.utils.file_uploads import safe_filename
from .models import BatchResult, JobResult


MIME_TYPES = {".epub": "application/epub+zip", ".m4a": "audio/mp4", ".heic": "image/heic", ".svg": "image/svg+xml"}


class OutputManager:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._used: set[str] = set()

    def path_for(self, display_name: str, extension: str, suffix: str) -> Path:
        stem = Path(safe_filename(display_name, "media")).stem
        base = safe_filename(f"{stem}_{suffix}.{extension}", f"media.{extension}")
        candidate, counter = base, 2
        while candidate.lower() in self._used:
            candidate = f"{Path(base).stem}_{counter}.{extension}"
            counter += 1
        self._used.add(candidate.lower())
        return self.root / candidate

    def package(self, results: list[JobResult], operation: str) -> BatchResult:
        source_bytes = sum(item.source_bytes for item in results)
        warnings = tuple(warning for item in results for warning in item.warnings)
        if len(results) == 1:
            result = results[0]
            media_type = MIME_TYPES.get(result.path.suffix.lower()) or mimetypes.guess_type(result.path.name)[0] or "application/octet-stream"
            return BatchResult(result.path, result.display_name, media_type, source_bytes, result.output_bytes, warnings)
        archive = self.root / f"media_{operation}_results.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as bundle:
            for result in results:
                bundle.write(result.path, arcname=Path(result.display_name).name)
        return BatchResult(archive, archive.name, "application/zip", source_bytes, archive.stat().st_size, warnings)
