from __future__ import annotations

import cv2
import numpy as np

from .profile import OCRProfile


def _order_quad(points: np.ndarray) -> np.ndarray:
    ordered = np.zeros((4, 2), dtype="float32")
    sums = points.sum(axis=1)
    differences = np.diff(points, axis=1).reshape(-1)
    ordered[0], ordered[2] = points[np.argmin(sums)], points[np.argmax(sums)]
    ordered[1], ordered[3] = points[np.argmin(differences)], points[np.argmax(differences)]
    return ordered


def find_document_quad(image: np.ndarray, profile: OCRProfile) -> np.ndarray | None:
    height, width = image.shape[:2]
    scale = min(1.0, 1100 / max(height, width))
    small = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    mask = ((hsv[:, :, 1] < 90) & (hsv[:, :, 2] > 90)).astype("uint8") * 255
    size = max(7, int(round(max(small.shape[:2]) * 0.015)) | 1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((size, size), np.uint8))
    contours = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    coverage = cv2.contourArea(contour) / max(1, small.shape[0] * small.shape[1])
    if not profile.document_min_coverage <= coverage <= profile.document_max_coverage:
        return None
    perimeter = cv2.arcLength(contour, True)
    for epsilon in (0.015, 0.02, 0.03, 0.04, 0.05):
        candidate = cv2.approxPolyDP(contour, epsilon * perimeter, True)
        if len(candidate) == 4 and cv2.isContourConvex(candidate):
            return _order_quad(candidate.reshape(4, 2).astype("float32") / scale)
    return None


def rectify_page(image: np.ndarray, profile: OCRProfile) -> tuple[np.ndarray, np.ndarray]:
    quad = find_document_quad(image, profile)
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


def resize_page(image: np.ndarray, inverse: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    longest = max(image.shape[:2])
    target = min(4200, max(3000, longest))
    scale = target / longest
    if abs(scale - 1.0) < 0.02:
        return image, inverse
    mode = cv2.INTER_CUBIC if scale > 1 else cv2.INTER_AREA
    resized = cv2.resize(image, None, fx=scale, fy=scale, interpolation=mode)
    scale_inverse = np.array([[1 / scale, 0, 0], [0, 1 / scale, 0], [0, 0, 1]], dtype="float32")
    return resized, inverse @ scale_inverse
