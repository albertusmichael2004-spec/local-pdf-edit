from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..models import JobOptions, MediaProbeResult


class MediaEngine(ABC):
    @abstractmethod
    def process(self, source: Path, output: Path, probe: MediaProbeResult, options: JobOptions) -> tuple[str, ...]:
        """Create and validate output, returning user-facing warnings."""
