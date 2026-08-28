from __future__ import annotations

import re
from statistics import median

from .models import OCRWord


def usable_word(
    word: OCRWord,
    page_width: int,
) -> bool:
    token = re.sub(
        r"[^\w]",
        "",
        word.text,
        flags=re.UNICODE,
    )

    if not token:
        return False

    text = word.text.strip()

    structural_marker = bool(
        re.fullmatch(
            r"(?:[\w+#-]{1,4}:|"
            r"\(?\d{1,3}[.)])",
            text,
            flags=re.UNICODE,
        )
    )

    if (
        structural_marker
        and word.left
        <= page_width * 0.35
    ):
        return True

    if word.confidence >= 35:
        return True

    return (
        word.confidence >= 20
        and len(token) >= 4
    )


def line_center(words: list[OCRWord]) -> float:
    return median(word.top + word.height / 2 for word in words)


def line_height(words: list[OCRWord]) -> float:
    return median(word.height for word in words)


def same_visual_line(words: list[OCRWord], word: OCRWord) -> bool:
    distance = abs(line_center(words) - (word.top + word.height / 2))
    height = min(line_height(words), word.height)
    left = min(item.left for item in words)
    right = max(item.left + item.width for item in words)
    horizontal = min(right, word.left + word.width) - max(left, word.left)
    staggered = horizontal <= min(word.width, right - left) * 0.12
    tolerance = height * (0.72 if staggered else 0.42)
    return distance <= max(4.0, tolerance)


def group_visual_lines(words: list[OCRWord]) -> list[list[OCRWord]]:
    lines: list[list[OCRWord]] = []
    ordered = sorted(words, key=lambda word: (word.top + word.height / 2, word.left))
    for word in ordered:
        candidates = [line for line in lines if same_visual_line(line, word)]
        if candidates:
            min(candidates, key=lambda line: abs(line_center(line) - word.top)).append(word)
        else:
            lines.append([word])
    for line in lines:
        line.sort(key=lambda item: item.left)
    return sorted(lines, key=lambda line: (line_center(line), line[0].left))
