from __future__ import annotations

from pathlib import Path

from backend.core.errors import MediaProcessingError
from .engines import EbookEngine, FFmpegEngine, ImageEngine, PDFEngineAdapter
from .models import JobOptions, MediaProbeResult


ALIASES = {"jpeg": "jpg", "tif": "tiff", "heif": "heic", "aif": "aiff", "matroska": "mkv"}


class JobPlanner:
    def __init__(self) -> None:
        self.engines = {"image": ImageEngine(), "video": FFmpegEngine(), "audio": FFmpegEngine(), "ebook": EbookEngine(), "pdf": PDFEngineAdapter()}

    def normalize(self, source: Path, probe: MediaProbeResult, options: JobOptions) -> JobOptions:
        target = options.target_format.lower().lstrip(".")
        if target == "keep":
            target = source.suffix.lower().lstrip(".") or probe.format
        target = ALIASES.get(target, target)
        return JobOptions(options.operation, target, options.quality, options.keep_metadata)

    def engine_for(self, probe: MediaProbeResult):
        try:
            return self.engines[probe.kind]
        except KeyError as exc:
            raise MediaProcessingError(f"No processing engine is available for {probe.kind} files.") from exc
