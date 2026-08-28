from __future__ import annotations

from backend.services.shared.ocr.models import OCRPage, OCRWord
from backend.services.shared.ocr.visual_lines import group_visual_lines, usable_word

from .generic_cleanup import clean_ocr_line


def _group_words_by_line(page: OCRPage) -> list[list[OCRWord]]:
    words = [word for word in page.words if usable_word(word, page.ocr_width)]
    if page.variant == "line-ensemble":
        line_ids = sorted({word.line for word in words})
        return [
            sorted((word for word in words if word.line == line_id), key=lambda word: word.paragraph)
            for line_id in line_ids
        ]
    return group_visual_lines(words)


def page_lines(page: OCRPage) -> list[str]:
    output: list[str] = []
    for words in _group_words_by_line(page):
        parts: list[str] = []
        previous: OCRWord | None = None
        for index, word in enumerate(words):
            gap = (
                word.left
                - (
                    previous.left
                    + previous.width
                )
                if previous
                else 999
            )

            tight_gap = (
                max(
                    4,
                    min(
                        previous.height,
                        word.height,
                    ) * 0.08,
                )
                if previous
                else 0
            )

            fragments = (
                min(
                    len(previous.text),
                    len(word.text),
                ) <= 2
                if previous
                else False
            )

            separator = (
                ""
                if (
                    previous
                    and fragments
                    and gap <= tight_gap
                )
                else " "
            )

            parts.append(
                separator
                + word.text
            )
            previous = word
        text = clean_ocr_line("".join(parts).strip())
        if text:
            output.append(text)
    return output


def page_text(page: OCRPage) -> str:
    return "\n".join(page_lines(page))
