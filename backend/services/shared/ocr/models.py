from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True, frozen=True)
class OCRWord:
    text: str
    confidence: float

    left: int
    top: int
    width: int
    height: int

    block: int
    paragraph: int
    line: int


@dataclass(slots=True)
class OCRPage:
    source_path: Path

    source_width: int
    source_height: int

    ocr_width: int
    ocr_height: int

    words: list[OCRWord]

    confidence: float
    psm: int
    variant: str


@dataclass(slots=True, frozen=True)
class PreparedOCRImage:
    source_size: tuple[int, int]
    ocr_size: tuple[int, int]
    variants: list[tuple[str, Path]]
    inverse_transform: list[list[float]]
