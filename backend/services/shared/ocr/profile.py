from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from backend.core.paths import PROJECT_ROOT


@dataclass(frozen=True, slots=True)
class OCRProfile:
    schema_version: int = 1
    name: str = "default"
    min_word_confidence: float = 20.0
    document_min_coverage: float = 0.35
    document_max_coverage: float = 0.96
    primary_psm: int = 3
    fallback_psm: int = 4
    clahe_clip_limit: float = 2.0
    deskew_max_angle: float = 8.0
    horizontal_padding_ratio: float = 0.01
    candidate_early_exit_score: float = 82.0
    denoise_strength: int = 8
    normalize_scale: int = 235
    sharpen_weight: float = 1.45

    def validate(self) -> "OCRProfile":
        checks = (
            (0 <= self.min_word_confidence <= 100, "min_word_confidence"),
            (0.1 <= self.document_min_coverage < self.document_max_coverage, "document coverage"),
            (self.document_max_coverage <= 0.995, "document_max_coverage"),
            (self.primary_psm in {3, 4, 6, 11, 12, 13}, "primary_psm"),
            (self.fallback_psm in {3, 4, 6, 11, 12, 13}, "fallback_psm"),
            (0.5 <= self.clahe_clip_limit <= 6, "clahe_clip_limit"),
            (0 <= self.deskew_max_angle <= 15, "deskew_max_angle"),
            (0 <= self.horizontal_padding_ratio <= 0.08, "horizontal_padding_ratio"),
            (0 <= self.candidate_early_exit_score <= 120, "candidate_early_exit_score"),
            (0 <= self.denoise_strength <= 30, "denoise_strength"),
            (180 <= self.normalize_scale <= 255, "normalize_scale"),
            (1 <= self.sharpen_weight <= 3, "sharpen_weight"),
        )
        invalid = [name for valid, name in checks if not valid]
        if invalid:
            raise ValueError("Invalid OCR profile fields: " + ", ".join(invalid))
        return self

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "OCRProfile":
        source = data.get("profile", data)
        if not isinstance(source, dict):
            raise ValueError("OCR profile must be a JSON object.")
        allowed = {field.name for field in fields(cls)}
        values = {key: value for key, value in source.items() if key in allowed}
        return cls(**values).validate()


def champion_path() -> Path:
    override = os.environ.get("OCR_PROFILE_PATH")
    return Path(override) if override else PROJECT_ROOT / "training/ocr/profiles/champion.json"


def load_profile(path: Path) -> OCRProfile:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return OCRProfile.from_dict(payload)


def load_active_profile() -> OCRProfile:
    path = champion_path()
    try:
        return load_profile(path) if path.is_file() else OCRProfile()
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return OCRProfile()
