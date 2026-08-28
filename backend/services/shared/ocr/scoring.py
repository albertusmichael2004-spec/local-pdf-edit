from __future__ import annotations

import re

from .models import OCRPage


def candidate_score(page: OCRPage) -> float:
    """Favor confident, complete text while rejecting fragmented OCR noise."""
    if not page.words:
        return -1.0
    tokens = [re.sub(r"[^\w]", "", word.text, flags=re.UNICODE) for word in page.words]
    useful_chars = sum(len(token) for token in tokens)
    fragments = sum(len(token) <= 1 for token in tokens)
    noise = sum(not token for token in tokens)
    weak = sum(word.confidence < 30 for word in page.words)
    mixed_case = sum(bool(re.search(r"[a-z][A-Z]|[A-Z][a-z][A-Z]", token)) for token in tokens)
    denominator = max(1, len(tokens))
    top = min(word.top for word in page.words)
    bottom = max(word.top + word.height for word in page.words)
    vertical_coverage = min(1.0, (bottom - top) / max(1, page.ocr_height))
    variant_bonus = 0.75 if page.variant == "normalized" else 0.0
    return (
        page.confidence
        + variant_bonus
        + min(12.0, useful_chars / 110)
        + vertical_coverage * 4
        - fragments / denominator * 18
        - noise / denominator * 28
        - weak / denominator * 12
        - mixed_case / denominator * 24
    )
