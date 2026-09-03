from __future__ import annotations

from pathlib import Path

from backend.core.config import settings
from backend.core.errors import MediaProcessingError
from backend.core.executables import find_ebook_convert
from backend.core.subprocesses import run_hidden
from .base import MediaEngine
from ..models import JobOptions, MediaProbeResult


class EbookEngine(MediaEngine):
    def process(self, source: Path, output: Path, probe: MediaProbeResult, options: JobOptions) -> tuple[str, ...]:
        executable = find_ebook_convert()
        if not executable:
            raise MediaProcessingError("Calibre ebook-convert is required for ebook conversion. Install Calibre and restart the app.")
        result = run_hidden(
            [executable, str(source), str(output)], capture_output=True, text=True,
            timeout=settings.media_timeout_seconds, shell=False,
        )
        if result.returncode or not output.exists() or not output.stat().st_size:
            detail = (result.stderr or "Calibre created no usable output.")[-1200:]
            raise MediaProcessingError(f"Ebook conversion failed for {source.name}: {detail}")
        if probe.format == "pdf" and options.target_format == "epub":
            return ("PDF to EPUB is lossy; reflow, tables, headers, and reading order may change.",)
        return ()
