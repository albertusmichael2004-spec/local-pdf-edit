from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class MediaProbeResult:
    kind: str
    format: str
    mime_type: str
    bytes: int
    details: dict[str, object] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class MediaSource:
    path: Path
    display_name: str


@dataclass(frozen=True)
class JobOptions:
    operation: str
    target_format: str
    quality: str = "balanced"
    keep_metadata: bool = True


@dataclass(frozen=True)
class JobResult:
    path: Path
    display_name: str
    source_bytes: int
    output_bytes: int
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class BatchResult:
    path: Path
    download_name: str
    media_type: str
    source_bytes: int
    output_bytes: int
    warnings: tuple[str, ...]
