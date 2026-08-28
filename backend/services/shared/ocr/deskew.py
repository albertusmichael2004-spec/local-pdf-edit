from __future__ import annotations

from statistics import median

import cv2
import numpy as np


def _baseline_angle(image: np.ndarray) -> float:
    height, width = image.shape[:2]
    scale = min(1.0, 1200 / max(height, width))
    small = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    dark = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    kernel_width = max(25, small.shape[1] // 40)
    rows = cv2.morphologyEx(
        dark, cv2.MORPH_CLOSE, np.ones((1, kernel_width), np.uint8)
    )
    lines = cv2.HoughLinesP(
        rows,
        1,
        np.pi / 720,
        threshold=45,
        minLineLength=max(80, small.shape[1] // 12),
        maxLineGap=max(15, small.shape[1] // 50),
    )
    if lines is None:
        return 0.0
    angles: list[float] = []

    # OpenCV versions may return HoughLinesP results as
    # either (N, 1, 4) or (N, 4). Normalize both forms.
    segments = np.asarray(lines).reshape(-1, 4)

    for x1, y1, x2, y2 in segments:
        angle = float(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
        if abs(angle) <= 8:
            angles.append(angle)
    return median(angles) if len(angles) >= 3 else 0.0


def deskew_page(image: np.ndarray, inverse: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    angle = _baseline_angle(image)
    if abs(angle) < 0.2:
        return image, inverse
    height, width = image.shape[:2]
    affine = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    rotated = cv2.warpAffine(
        image, affine, (width, height), flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255),
    )
    transform = np.vstack((affine, (0.0, 0.0, 1.0))).astype("float32")
    return rotated, inverse @ np.linalg.inv(transform)
