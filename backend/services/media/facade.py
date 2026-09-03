from __future__ import annotations

from pathlib import Path

from backend.core.errors import MediaProcessingError
from .capabilities import targets_for
from .models import BatchResult, JobOptions, MediaProbeResult, MediaSource
from .output_manager import OutputManager
from .planner import JobPlanner
from .probe import probe_media
from .runner import JobRunner


class MediaJobFacade:
    def __init__(self, runner: JobRunner | None = None) -> None:
        self.planner = runner.planner if runner else JobPlanner()
        self.runner = runner or JobRunner(self.planner)

    def probe(self, sources: list[MediaSource]) -> list[tuple[MediaSource, MediaProbeResult]]:
        if not sources:
            raise MediaProcessingError("Upload at least one file.")
        return [(source, probe_media(source.path)) for source in sources]

    def process(
        self,
        sources: list[MediaSource],
        output_root: Path,
        options: JobOptions,
        allowed_kinds: set[str],
    ) -> BatchResult:
        probed = self.probe(sources)
        unexpected = sorted({probe.kind for _, probe in probed} - allowed_kinds)
        if unexpected:
            raise MediaProcessingError(f"This tool does not accept detected type(s): {', '.join(unexpected)}.")
        output = OutputManager(output_root)
        jobs = []
        for source, probe in probed:
            normalized = self.planner.normalize(source.path, probe, options)
            supported = {item["format"] for item in targets_for(probe)}
            if normalized.target_format not in supported:
                raise MediaProcessingError(f"{normalized.target_format.upper()} is not available for {source.display_name} on this computer.")
            path = output.path_for(source.display_name, normalized.target_format, options.operation)
            jobs.append((source, probe, path, normalized))
        return output.package(self.runner.run(jobs), options.operation)
