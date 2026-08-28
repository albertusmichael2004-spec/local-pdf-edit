from __future__ import annotations

import cv2
import numpy as np

from .models import OCRWord


def map_words_to_source(words: list[OCRWord], inverse_transform: list[list[float]]) -> list[OCRWord]:
    inverse = np.asarray(inverse_transform, dtype="float32")
    mapped: list[OCRWord] = []
    for word in words:
        right, bottom = word.left + word.width, word.top + word.height
        corners = np.array([[[word.left, word.top], [right, word.top], [right, bottom], [word.left, bottom]]], dtype="float32")
        points = cv2.perspectiveTransform(corners, inverse)[0]
        left, top = np.floor(points.min(axis=0)).astype(int)
        right, bottom = np.ceil(points.max(axis=0)).astype(int)
        mapped.append(OCRWord(
            text=word.text,
            confidence=word.confidence,
            left=max(0, left),
            top=max(0, top),
            width=max(1, right - left),
            height=max(1, bottom - top),
            block=word.block,
            paragraph=word.paragraph,
            line=word.line,
        ))
    return mapped
