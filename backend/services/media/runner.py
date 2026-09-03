from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from contextvars import copy_context
from pathlib import Path

from backend.core.config import settings
from backend.core.progress import report_fraction, report_progress
from .models import JobOptions, JobResult, MediaProbeResult, MediaSource
from .planner import JobPlanner


class JobRunner:
    def __init__(self, planner: JobPlanner | None = None, max_workers: int | None = None) -> None:
        self.planner = planner or JobPlanner()
        self.max_workers = max_workers or settings.media_workers

    def run(self, jobs: list[tuple[MediaSource, MediaProbeResult, Path, JobOptions]]) -> list[JobResult]:
        workers = min(self.max_workers, len(jobs))
        report_progress("Starting media workers", percent=24, detail=f"{len(jobs)} job(s)")
        with ThreadPoolExecutor(max_workers=max(1, workers), thread_name_prefix="media-job") as pool:
            futures = {
                pool.submit(copy_context().run, self._run_one, job): index
                for index, job in enumerate(jobs)
            }
            results: list[JobResult | None] = [None] * len(jobs)
            for completed, future in enumerate(as_completed(futures), start=1):
                results[futures[future]] = future.result()
                report_fraction("Processing media files", completed, len(jobs), 26, 92)
            return [result for result in results if result is not None]

    def _run_one(self, job: tuple[MediaSource, MediaProbeResult, Path, JobOptions]) -> JobResult:
        source, probe, output, options = job
        engine = self.planner.engine_for(probe)
        warnings = tuple(engine.process(source.path, output, probe, options))
        if (
            options.operation == "compressed"
            and options.quality == "extreme"
            and source.path.stat().st_size
            and output.stat().st_size > source.path.stat().st_size * 0.30
        ):
            reduction = (1 - output.stat().st_size / source.path.stat().st_size) * 100
            warnings += (
                f"Extreme mode targeted at least 70% reduction but achieved {max(0, reduction):.1f}%. "
                "The source may already be efficiently compressed.",
            )
        return JobResult(output, output.name, source.path.stat().st_size, output.stat().st_size, warnings)
