from __future__ import annotations

from dataclasses import dataclass

@dataclass
class PageCompare:
    page: int
    exists_left: bool
    exists_right: bool
    text_exact: bool
    word_sequence_exact: bool
    character_exact: bool
    left_characters: int
    right_characters: int
    character_similarity: float
    chars_inserted: int
    chars_deleted: int
    chars_replaced: int
    left_words: int
    right_words: int
    word_similarity: float
    words_inserted: int
    words_deleted: int
    words_replaced: int
    pixel_difference: float
    visually_identical: bool
    diff_image_name: str | None
    word_changes_preview: list[dict]
    character_changes_preview: list[dict]
