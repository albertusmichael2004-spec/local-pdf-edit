from dataclasses import replace
from pathlib import Path

from backend.services.convert_to_pdf.jpg_to_text_to_pdf.text_layout import page_lines
from backend.services.shared.ocr.line_ensemble import merge_page_lines
from backend.services.shared.ocr.models import OCRPage, OCRWord
from backend.services.shared.ocr.visual_lines import group_visual_lines


def _word(text: str, confidence: float, left: int, top: int) -> OCRWord:
    return OCRWord(text, confidence, left, top, max(30, len(text) * 20), 40, 1, 1, 1)


def _page(words: list[OCRWord], psm: int) -> OCRPage:
    return OCRPage(Path("page.jpg"), 1000, 1400, 1000, 1400, words, 90, psm, "normalized")


def test_line_ensemble_selects_complete_line_and_recovers_label():
    layout = _page([_word("P:", 80, 30, 100), _word("Saudara", 95, 180, 100)], 3)
    sparse = _page(
        [_word("Saudara", 93, 180, 102), _word("Fransiskus", 93, 360, 102)],
        11,
    )
    merged = merge_page_lines([layout, sparse])
    assert [word.text for word in sorted(merged.words, key=lambda word: word.left)] == [
        "P:", "Saudara", "Fransiskus",
    ]


def test_visual_lines_do_not_merge_adjacent_tall_italic_rows():
    first = _word("Terpujilah", 95, 100, 100)
    second = _word("dengannya", 95, 100, 150)
    first = OCRWord(first.text, first.confidence, first.left, first.top, first.width, 65, 1, 1, 1)
    second = OCRWord(second.text, second.confidence, second.left, second.top, second.width, 65, 2, 1, 1)
    assert len(group_visual_lines([first, second])) == 2


def test_line_clusters_keep_adjacent_rows_from_each_candidate_separate():
    first = _page([_word("alpha", 95, 100, 100), _word("beta", 95, 100, 160)], 3)
    second = _page([_word("alpha", 94, 100, 130), _word("beta", 94, 100, 190)], 11)
    assert len(merge_page_lines([first, second]).words) == 2


def test_export_uses_stable_line_ids_after_perspective_mapping():
    first = _page([_word("baris", 95, 100, 100), _word("satu", 95, 220, 100)], 3)
    second = _page([_word("baris", 95, 100, 170), _word("dua", 95, 220, 170)], 11)
    merged = merge_page_lines([first, second])
    merged.words = [
        replace(word, top=word.top + (100 if word.left > 150 else 0))
        for word in merged.words
    ]
    assert page_lines(merged) == ["baris satu", "baris dua"]
