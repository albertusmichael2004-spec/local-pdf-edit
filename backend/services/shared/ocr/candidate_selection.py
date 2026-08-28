from __future__ import annotations

from .models import OCRPage
from .scoring import candidate_score


def select_best_candidate(
    pages: list[OCRPage],
) -> OCRPage:
    """
    Select one complete OCR interpretation.

    OCR candidates may come from different preprocessing
    variants or Tesseract segmentation modes.

    We deliberately avoid merging unrelated OCR lines here.
    """

    if not pages:
        raise ValueError(
            "At least one OCR candidate is required."
        )

    scored = [
        (
            candidate_score(page),
            page,
        )
        for page in pages
    ]

    best_score, best_page = max(
        scored,
        key=lambda item: item[0],
    )

    normalized = [
        item
        for item in scored
        if item[1].variant == "normalized"
    ]

    if normalized:
        normalized_score, normalized_page = max(
            normalized,
            key=lambda item: item[0],
        )

        # Prefer the least transformed source when the
        # difference is statistically insignificant.
        if (
            normalized_score
            >= best_score - 1.25
        ):
            return normalized_page

    return best_page
