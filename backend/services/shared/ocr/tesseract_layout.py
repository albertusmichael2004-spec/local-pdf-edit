from __future__ import annotations

from pathlib import Path

from backend.core.errors import OCRError

from .candidate_selection import select_best_candidate
from .coordinates import map_words_to_source
from .languages import resolve_ocr_language
from .models import OCRPage, PreparedOCRImage
from .preprocess import prepare_ocr_variants
from .profile import OCRProfile
from .scoring import candidate_score
from .search_plan import SearchSpec, fallback_search_plan, initial_search_plan
from .tesseract_tsv import run_tsv


def _recognize(
    spec: SearchSpec,
    prepared: PreparedOCRImage,
    source_path: Path,
    executable: str,
    language: str,
    tessdata_dir: Path | None,
    profile: OCRProfile,
) -> OCRPage:
    variant_name, image_path, psm = spec
    words, confidence = run_tsv(image_path, executable, language, psm, tessdata_dir)
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
        min_word_confidence=profile.min_word_confidence,
    )


def recognize_best_page(
    source_path: Path,
    workspace: Path,
    tesseract_executable: str,
    language: str = "auto",
    quality: str = "accurate",
    profile: OCRProfile | None = None,
) -> OCRPage:
    profile = (profile or OCRProfile()).validate()
    prepared = prepare_ocr_variants(source_path, workspace, profile)
    selected_language, tessdata_dir = resolve_ocr_language(language)

    def run(spec: SearchSpec) -> OCRPage:
        return _recognize(
            spec, prepared, source_path, tesseract_executable,
            selected_language, tessdata_dir, profile,
        )

    candidates = [
        run(spec) for spec in initial_search_plan(quality, prepared.variants, profile)
    ]
    if quality == "accurate":
        initial = select_best_candidate(candidates)
        if candidate_score(initial) < profile.candidate_early_exit_score:
            candidates.extend(
                run(spec) for spec in fallback_search_plan(prepared.variants, profile)
            )
    best = select_best_candidate(candidates)
    if not best.words:
        raise OCRError("No readable text was detected.")
    best.words = map_words_to_source(best.words, prepared.inverse_transform)
    best.ocr_width, best.ocr_height = prepared.source_size
    return best
