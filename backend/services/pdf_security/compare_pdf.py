from __future__ import annotations

from dataclasses import asdict
from difflib import SequenceMatcher
import json
from pathlib import Path
import zipfile

import fitz

from backend.core.errors import SecurityError
from backend.services.pdf_security.sha256_pdf import sha256_file
from backend.services.shared.comparison.models import PageCompare
from backend.services.shared.comparison.report import build_report_html
from backend.services.shared.comparison.text_diff import operation_counts, tokenize_words
from backend.services.shared.comparison.visual_diff import render_diff

def compare_pdfs_detailed(
    left_path: Path,
    right_path: Path,
    dpi: int = 110,
    include_diff_payloads: bool = False,
) -> tuple[dict, dict[str, bytes]]:
    """Compare PDFs at byte, page, text, word, character and rendered-image level."""
    try:
        left_hash = sha256_file(left_path)
        right_hash = sha256_file(right_path)
        diff_payloads: dict[str, bytes] = {}

        with fitz.open(left_path) as left, fitz.open(right_path) as right:
            if left.needs_pass or right.needs_pass:
                raise SecurityError("Unlock encrypted PDFs before comparing them.")
            max_pages = max(left.page_count, right.page_count)
            results: list[PageCompare] = []
            scale = dpi / 72.0

            for idx in range(max_pages):
                exists_left = idx < left.page_count
                exists_right = idx < right.page_count
                if not exists_left or not exists_right:
                    ltext = left[idx].get_text("text") if exists_left else ""
                    rtext = right[idx].get_text("text") if exists_right else ""
                    lwords, rwords = tokenize_words(ltext), tokenize_words(rtext)
                    ci, cd, cr, cprev = operation_counts(ltext, rtext)
                    wi, wd, wr, wprev = operation_counts(lwords, rwords)
                    results.append(PageCompare(
                        page=idx + 1,
                        exists_left=exists_left,
                        exists_right=exists_right,
                        text_exact=False,
                        word_sequence_exact=False,
                        character_exact=False,
                        left_characters=len(ltext), right_characters=len(rtext),
                        character_similarity=round(SequenceMatcher(None, ltext, rtext, autojunk=False).ratio(), 6),
                        chars_inserted=ci, chars_deleted=cd, chars_replaced=cr,
                        left_words=len(lwords), right_words=len(rwords),
                        word_similarity=round(SequenceMatcher(None, lwords, rwords, autojunk=False).ratio(), 6),
                        words_inserted=wi, words_deleted=wd, words_replaced=wr,
                        pixel_difference=1.0, visually_identical=False, diff_image_name=None,
                        word_changes_preview=wprev, character_changes_preview=cprev,
                    ))
                    continue

                lp, rp = left[idx], right[idx]
                ltext = lp.get_text("text") or ""
                rtext = rp.get_text("text") or ""
                lwords = tokenize_words(ltext)
                rwords = tokenize_words(rtext)
                char_matcher = SequenceMatcher(None, ltext, rtext, autojunk=False)
                word_matcher = SequenceMatcher(None, lwords, rwords, autojunk=False)
                ci, cd, cr, cprev = operation_counts(ltext, rtext)
                wi, wd, wr, wprev = operation_counts(lwords, rwords)
                pixel_difference, visually_identical, diff_payload = render_diff(lp, rp, scale)
                diff_name = None
                if diff_payload is not None:
                    diff_name = f"diff/page_{idx + 1:03d}.png"
                    if include_diff_payloads:
                        diff_payloads[diff_name] = diff_payload
                results.append(PageCompare(
                    page=idx + 1,
                    exists_left=True, exists_right=True,
                    text_exact=ltext == rtext,
                    word_sequence_exact=lwords == rwords,
                    character_exact=ltext == rtext,
                    left_characters=len(ltext), right_characters=len(rtext),
                    character_similarity=round(char_matcher.ratio(), 6),
                    chars_inserted=ci, chars_deleted=cd, chars_replaced=cr,
                    left_words=len(lwords), right_words=len(rwords),
                    word_similarity=round(word_matcher.ratio(), 6),
                    words_inserted=wi, words_deleted=wd, words_replaced=wr,
                    pixel_difference=pixel_difference,
                    visually_identical=visually_identical,
                    diff_image_name=diff_name,
                    word_changes_preview=wprev,
                    character_changes_preview=cprev,
                ))

            serial_results = [asdict(r) for r in results]
            differing = [
                r for r in results
                if not (r.text_exact and r.word_sequence_exact and r.character_exact and r.visually_identical and r.exists_left and r.exists_right)
            ]
            exact_text_pages = sum(1 for r in results if r.text_exact and r.exists_left and r.exists_right)
            exact_word_pages = sum(1 for r in results if r.word_sequence_exact and r.exists_left and r.exists_right)
            exact_char_pages = sum(1 for r in results if r.character_exact and r.exists_left and r.exists_right)
            visual_same_pages = sum(1 for r in results if r.visually_identical and r.exists_left and r.exists_right)
            summary = {
                "byte_identical": left_hash == right_hash,
                "sha256_left": left_hash,
                "sha256_right": right_hash,
                "left_pages": left.page_count,
                "right_pages": right.page_count,
                "total_compared_pages": max_pages,
                "different_pages": len(differing),
                "exact_text_pages": exact_text_pages,
                "exact_word_pages": exact_word_pages,
                "exact_character_pages": exact_char_pages,
                "visually_identical_pages": visual_same_pages,
                "all_extracted_text_exact": left.page_count == right.page_count and exact_text_pages == max_pages,
                "all_word_sequences_exact": left.page_count == right.page_count and exact_word_pages == max_pages,
                "all_characters_exact": left.page_count == right.page_count and exact_char_pages == max_pages,
                "all_pages_visually_identical": left.page_count == right.page_count and visual_same_pages == max_pages,
                "page_results": serial_results,
                "comparison_note": (
                    "Text/word/character comparison uses text extracted by PyMuPDF. Character exactness includes whitespace and line breaks. "
                    "Visual comparison renders pages locally and can detect layout/image changes even when text is unchanged."
                ),
            }
            return summary, diff_payloads
    except SecurityError:
        raise
    except Exception as exc:
        raise SecurityError(f"PDF comparison failed: {exc}") from exc

def compare_pdfs_to_zip(left_path: Path, right_path: Path, output_zip: Path, dpi: int = 110) -> dict:
    summary, diff_payloads = compare_pdfs_detailed(left_path, right_path, dpi=dpi, include_diff_payloads=True)
    try:
        report = build_report_html(summary, dpi)
        with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("summary.json", json.dumps(summary, indent=2, ensure_ascii=False))
            archive.writestr("comparison_report.html", report)
            for name, data in diff_payloads.items():
                archive.writestr(name, data)
        return summary
    except Exception as exc:
        raise SecurityError(f"Could not create comparison report ZIP: {exc}") from exc
