from __future__ import annotations

import cv2
import numpy as np


def remove_long_rules(gray: np.ndarray) -> np.ndarray:
    """Erase page rules that Tesseract commonly turns into repeated punctuation."""
    dark = cv2.threshold(gray, 175, 255, cv2.THRESH_BINARY_INV)[1]
    kernel = np.ones((1, max(50, gray.shape[1] // 12)), np.uint8)
    rules = cv2.morphologyEx(dark, cv2.MORPH_OPEN, kernel)
    rules = cv2.dilate(rules, np.ones((5, 3), np.uint8))
    cleaned = gray.copy()
    cleaned[rules > 0] = 255
    return cleaned


def isolate_text_lines(gray: np.ndarray, horizontal_padding_ratio: float = 0.01) -> np.ndarray:
    """Hide large illustrations while retaining compact printed text rows."""
    height, width = gray.shape
    _, binary = cv2.threshold(
        gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU
    )
    kernel_width = max(25, width // 85)
    joined = cv2.morphologyEx(
        binary,
        cv2.MORPH_CLOSE,
        np.ones((3, kernel_width), np.uint8),
    )
    contours = cv2.findContours(joined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]
    mask = np.zeros_like(gray)
    min_width = max(65, width // 30)
    max_height = max(145, height // 24)
    vertical_padding = max(
        16,
        height // 180,
    )

    horizontal_padding = max(18, int(width * horizontal_padding_ratio))

    for contour in contours:
        (
            left,
            top,
            box_width,
            box_height,
        ) = cv2.boundingRect(
            contour
        )

        aspect = (
            box_width
            / max(
                1,
                box_height,
            )
        )

        if (
            box_width < min_width
            or box_height > max_height
            or aspect < 1.35
        ):
            continue

        x1 = max(
            0,
            left
            - horizontal_padding,
        )

        x2 = min(
            width,
            left
            + box_width
            + horizontal_padding,
        )

        y1 = max(
            0,
            top
            - vertical_padding,
        )

        y2 = min(
            height,
            top
            + box_height
            + vertical_padding,
        )

        mask[
            y1:y2,
            x1:x2,
        ] = 255
    canvas = np.full_like(gray, 255)
    canvas[mask > 0] = gray[mask > 0]
    return canvas
