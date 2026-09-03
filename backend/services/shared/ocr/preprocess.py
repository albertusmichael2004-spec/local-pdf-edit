from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

from .deskew import deskew_page
from .document_geometry import rectify_page, resize_page
from .models import PreparedOCRImage
from .profile import OCRProfile
from .text_mask import isolate_text_lines, remove_long_rules


def _load_source(source_path: Path) -> tuple[tuple[int, int], np.ndarray]:
    with Image.open(source_path) as source:
        source = ImageOps.exif_transpose(source).convert("RGB")
        return source.size, cv2.cvtColor(np.array(source), cv2.COLOR_RGB2BGR)


def _enhance(gray: np.ndarray, profile: OCRProfile) -> tuple[np.ndarray, np.ndarray]:
    gentle = cv2.createCLAHE(profile.clahe_clip_limit, (8, 8)).apply(gray)
    if profile.denoise_strength:
        gentle = cv2.fastNlMeansDenoising(
            gentle, None, profile.denoise_strength, 7, 21,
        )
    background = cv2.GaussianBlur(gray, (0, 0), 35)
    normalized = cv2.divide(gray, background, scale=profile.normalize_scale)
    contrast = cv2.createCLAHE(profile.clahe_clip_limit, (8, 8)).apply(normalized)
    blur = cv2.GaussianBlur(contrast, (0, 0), 1.2)
    sharp = cv2.addWeighted(
        contrast, profile.sharpen_weight, blur, 1 - profile.sharpen_weight, 0,
    )
    return remove_long_rules(sharp), gentle


def prepare_ocr_variants(
    source_path: Path, workspace: Path, profile: OCRProfile | None = None,
) -> PreparedOCRImage:
    profile = (profile or OCRProfile()).validate()
    workspace.mkdir(parents=True, exist_ok=True)
    source_size, image = _load_source(source_path)
    page, inverse = rectify_page(image, profile)
    page, inverse = deskew_page(page, inverse, profile.deskew_max_angle)
    page, inverse = resize_page(page, inverse)
    sharp, gentle = _enhance(cv2.cvtColor(page, cv2.COLOR_BGR2GRAY), profile)
    variants = [
        ("normalized", workspace / "normalized.png"),
        ("text-lines", workspace / "text-lines.png"),
        ("gentle", workspace / "gentle.png"),
    ]
    cv2.imwrite(str(variants[0][1]), sharp)
    masked = isolate_text_lines(sharp, profile.horizontal_padding_ratio)
    cv2.imwrite(str(variants[1][1]), masked)
    cv2.imwrite(str(variants[2][1]), gentle)
    height, width = sharp.shape
    return PreparedOCRImage(source_size, (width, height), variants, inverse.tolist())
