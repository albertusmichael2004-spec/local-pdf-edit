from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CompressionProfile:
    dpi: int
    jpeg_quality: int
    mono_dpi: int
    jpeg_qfactor: float = 0.5
    force_jpeg_reencode: bool = False


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
    "extreme": CompressionProfile(
        dpi=150,
        jpeg_quality=42,
        mono_dpi=300,
        jpeg_qfactor=0.90,
        force_jpeg_reencode=True,
    ),
    "recommended": CompressionProfile(
        dpi=150,
        jpeg_quality=74,
        mono_dpi=300,
        jpeg_qfactor=0.55,
        force_jpeg_reencode=True,
    ),
    "less": CompressionProfile(
        dpi=220,
        jpeg_quality=88,
        mono_dpi=450,
        jpeg_qfactor=0.35,
        force_jpeg_reencode=False,
    ),
}
