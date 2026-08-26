from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CompressionProfile:
    dpi: int
    jpeg_quality: int
    mono_dpi: int


@dataclass(frozen=True)
class CompressionResult:
    output_path: Path
    original_bytes: int
    output_bytes: int
    mode: str
    achieved_target: bool | None = None
    target_min_bytes: int | None = None
    target_max_bytes: int | None = None
    note: str = ""

    @property
    def reduction_percent(self) -> float:
        if self.original_bytes <= 0:
            return 0.0
        return max(0.0, (1 - self.output_bytes / self.original_bytes) * 100)


PRESETS: dict[str, CompressionProfile] = {
    "extreme": CompressionProfile(dpi=72, jpeg_quality=42, mono_dpi=180),
    "recommended": CompressionProfile(dpi=150, jpeg_quality=74, mono_dpi=300),
    "less": CompressionProfile(dpi=220, jpeg_quality=88, mono_dpi=450),
}
