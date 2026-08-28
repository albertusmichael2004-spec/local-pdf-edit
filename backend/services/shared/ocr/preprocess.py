from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

from .deskew import deskew_page
from .models import PreparedOCRImage
from .text_mask import isolate_text_lines, remove_long_rules


def _order_quad(points: np.ndarray) -> np.ndarray:
    ordered = np.zeros((4, 2), dtype="float32")
    sums = points.sum(axis=1)
    differences = np.diff(points, axis=1).reshape(-1)
    ordered[0], ordered[2] = points[np.argmin(sums)], points[np.argmax(sums)]
    ordered[1], ordered[3] = points[np.argmin(differences)], points[np.argmax(differences)]
    return ordered


def _find_document_quad(image: np.ndarray) -> np.ndarray | None:
    height, width = image.shape[:2]
    scale = min(1.0, 1100 / max(height, width))
    small = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    mask = ((hsv[:, :, 1] < 90) & (hsv[:, :, 2] > 90)).astype("uint8") * 255
    kernel_size = max(7, int(round(max(small.shape[:2]) * 0.015)) | 1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((kernel_size, kernel_size), np.uint8))
    contours = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]
    if not contours:
        return None
    contour = max(
        contours,
        key=cv2.contourArea,
    )

    image_area = max(
        1,
        small.shape[0]
        * small.shape[1],
    )

    coverage = (
        cv2.contourArea(contour)
        / image_area
    )

    # A photographed document can occupy almost the
    # entire camera frame. Reject only clearly tiny
    # or effectively full-frame masks.
    if (
        coverage < 0.35
        or coverage > 0.96
    ):
        return None

    perimeter = cv2.arcLength(
        contour,
        True,
    )

    quad = None

    for epsilon in (
        0.015,
        0.02,
        0.03,
        0.04,
        0.05,
    ):
        candidate = cv2.approxPolyDP(
            contour,
            epsilon * perimeter,
            True,
        )

        if (
            len(candidate) == 4
            and cv2.isContourConvex(
                candidate
            )
        ):
            quad = candidate
            break

    if quad is None:
        return None

    return _order_quad(
        quad
        .reshape(4, 2)
        .astype("float32")
        / scale
    )


def _rectify(image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    quad = _find_document_quad(image)
    if quad is None:
        return image, np.eye(3, dtype="float32")
    top_left, top_right, bottom_right, bottom_left = quad
    width = int(max(np.linalg.norm(bottom_right - bottom_left), np.linalg.norm(top_right - top_left)))
    height = int(max(np.linalg.norm(top_right - bottom_right), np.linalg.norm(top_left - bottom_left)))
    if width < 600 or height < 800:
        return image, np.eye(3, dtype="float32")
    target = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype="float32")
    transform = cv2.getPerspectiveTransform(quad, target)
    page = cv2.warpPerspective(image, transform, (width, height), borderValue=(255, 255, 255))
    return page, np.linalg.inv(transform).astype("float32")


def _resize(image: np.ndarray, inverse: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    longest = max(image.shape[:2])
    target = min(4200, max(3000, longest))
    scale = target / longest
    if abs(scale - 1.0) < 0.02:
        return image, inverse
    interpolation = cv2.INTER_CUBIC if scale > 1 else cv2.INTER_AREA
    resized = cv2.resize(image, None, fx=scale, fy=scale, interpolation=interpolation)
    scale_inverse = np.array([[1 / scale, 0, 0], [0, 1 / scale, 0], [0, 0, 1]], dtype="float32")
    return resized, inverse @ scale_inverse


def prepare_ocr_variants(source_path: Path, workspace: Path) -> PreparedOCRImage:
    workspace.mkdir(parents=True, exist_ok=True)
    with Image.open(source_path) as source:
        source = ImageOps.exif_transpose(source).convert("RGB")
        source_size = source.size
        image = cv2.cvtColor(np.array(source), cv2.COLOR_RGB2BGR)
    page, inverse = _rectify(image)
    page, inverse = deskew_page(page, inverse)
    page, inverse = _resize(page, inverse)
    gray = cv2.cvtColor(page, cv2.COLOR_BGR2GRAY)
    gentle = cv2.createCLAHE(2.0, (8, 8)).apply(gray)
    gentle = cv2.fastNlMeansDenoising(gentle, None, 8, 7, 21)
    background = cv2.GaussianBlur(gray, (0, 0), 35)
    normalized = cv2.divide(gray, background, scale=235)
    contrast = cv2.createCLAHE(2.0, (8, 8)).apply(normalized)
    sharp = cv2.addWeighted(contrast, 1.45, cv2.GaussianBlur(contrast, (0, 0), 1.2), -0.45, 0)
    sharp = remove_long_rules(sharp)
    variants = [
        ("normalized", workspace / "normalized.png"),
        ("text-lines", workspace / "text-lines.png"),
        ("gentle", workspace / "gentle.png"),
    ]
    cv2.imwrite(str(variants[0][1]), sharp)
    cv2.imwrite(str(variants[1][1]), isolate_text_lines(sharp))
    cv2.imwrite(str(variants[2][1]), gentle)
    height, width = sharp.shape
    return PreparedOCRImage(source_size, (width, height), variants, inverse.tolist())
