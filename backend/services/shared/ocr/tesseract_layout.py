from __future__ import annotations

from pathlib import Path

from backend.core.errors import OCRError

from .coordinates import map_words_to_source
from .candidate_selection import select_best_candidate
from .scoring import candidate_score
from .languages import resolve_ocr_language
from .models import OCRPage
from .preprocess import prepare_ocr_variants
from .tesseract_tsv import run_tsv


def _search_plan(
    quality: str,
    variants: list[tuple[str, Path]],
) -> list[tuple[str, Path, int]]:
    by_name = dict(variants)

    if quality == "fast":
        return [
            (
                "normalized",
                by_name["normalized"],
                3,
            )
        ]

    if quality == "maximum":
        return [
            (
                variant_name,
                variant_path,
                psm,
            )
            for variant_name in (
                "normalized",
                "text-lines",
                "gentle",
            )
            if (
                variant_path
                := by_name.get(
                    variant_name
                )
            ) is not None
            for psm in (
                3,
                4,
            )
        ]

    return [
        (
            "normalized",
            by_name["normalized"],
            3,
        ),
        (
            "normalized",
            by_name["normalized"],
            4,
        ),
    ]


def recognize_best_page(
    source_path: Path,
    workspace: Path,
    tesseract_executable: str,
    language: str = "auto",
    quality: str = "accurate",
) -> OCRPage:
    prepared = prepare_ocr_variants(source_path, workspace)
    selected_language, tessdata_dir = resolve_ocr_language(language)
    def recognize(spec: tuple[str, Path, int]) -> OCRPage:
        variant_name, image_path, psm = spec
        words, confidence = run_tsv(
            image_path, tesseract_executable, selected_language, psm, tessdata_dir,
        )
        return OCRPage(
            source_path=source_path,
            source_width=prepared.source_size[0],
            source_height=prepared.source_size[1],
            ocr_width=prepared.ocr_size[0],
            ocr_height=prepared.ocr_size[1],
            words=words,
            confidence=confidence,
            psm=psm,
            variant=variant_name,
        )

    candidates = [
        recognize(spec)
        for spec in _search_plan(
            quality,
            prepared.variants,
        )
    ]

    if quality == "accurate":
        best_initial = (
            select_best_candidate(
                candidates
            )
        )

        # Only pay for additional preprocessing when
        # the primary interpretations are genuinely weak.
        if (
            candidate_score(
                best_initial
            )
            < 82
        ):
            by_name = dict(
                prepared.variants
            )

            for variant_name in (
                "text-lines",
                "gentle",
            ):
                variant_path = (
                    by_name.get(
                        variant_name
                    )
                )

                if variant_path is None:
                    continue

                candidates.extend(
                    recognize(
                        (
                            variant_name,
                            variant_path,
                            psm,
                        )
                    )
                    for psm in (
                        3,
                        4,
                    )
                )

    best = select_best_candidate(
        candidates
    )
    if not best.words:
        raise OCRError("No readable text was detected.")
    best.words = map_words_to_source(best.words, prepared.inverse_transform)
    best.ocr_width, best.ocr_height = prepared.source_size
    return best
