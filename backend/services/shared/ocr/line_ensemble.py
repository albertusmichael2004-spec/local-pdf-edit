from __future__ import annotations

import re
from dataclasses import replace
from .labels import speaker_label
from .models import OCRPage, OCRWord
from .visual_lines import line_center, line_height, usable_word


def _same_physical_line(first: list[OCRWord], second: list[OCRWord]) -> bool:
    distance = abs(line_center(first) - line_center(second))
    return distance <= max(8.0, min(line_height(first), line_height(second)) * 0.95)


def _candidate_lines(page: OCRPage) -> list[list[OCRWord]]:
    groups: dict[tuple[int, int, int], list[OCRWord]] = {}
    for word in page.words:
        if usable_word(word, page.ocr_width):
            groups.setdefault((word.block, word.paragraph, word.line), []).append(word)
    lines = sorted((sorted(words, key=lambda word: word.left) for words in groups.values()), key=line_center)
    merged: list[list[OCRWord]] = []
    for line in lines:
        matches = [row for row in merged if abs(line_center(row) - line_center(line))
                   <= max(6.0, min(line_height(row), line_height(line)) * 0.55)]
        if matches:
            matches[-1].extend(line)
            matches[-1].sort(key=lambda word: word.left)
        else:
            merged.append(line)
    return merged


def _line_score(words: list[OCRWord], page_width: int) -> float:
    tokens = [re.sub(r"[^\w]", "", word.text) for word in words]
    characters = sum(map(len, tokens))
    confidence = sum(word.confidence * max(1, len(token)) for word, token in zip(words, tokens))
    confidence /= max(1, sum(max(1, len(token)) for token in tokens))
    fragments = sum(len(token) <= 1 for token in tokens)
    mixed_case = sum(bool(re.search(r"[a-z][A-Z]|[A-Z][a-z][A-Z]", token)) for token in tokens)
    label_bonus = 5 if any(speaker_label(word, page_width) for word in words) else 0
    list_bonus = 5 if any(re.fullmatch(r"[a-z]\.", word.text.lower()) for word in words) else 0
    return confidence * 0.5 + characters * 0.55 + label_bonus + list_bonus - fragments * 3 - mixed_case * 12


def _same_detection(first: OCRWord, second: OCRWord) -> bool:
    vertical = abs((first.top + first.height / 2) - (second.top + second.height / 2))
    horizontal = min(first.left + first.width, second.left + second.width) - max(first.left, second.left)
    if vertical > min(first.height, second.height) * 0.7 or horizontal <= 0:
        return False
    first_text = re.sub(r"[^\w]", "", first.text.lower())
    second_text = re.sub(r"[^\w]", "", second.text.lower())
    return first_text in second_text or second_text in first_text


def _recover_label(chosen: list[OCRWord], alternatives: list[list[OCRWord]], width: int) -> None:
    if any(speaker_label(word, width) for word in chosen):
        return
    labels = [word for line in alternatives for word in line if speaker_label(word, width)]
    if labels:
        chosen.append(max(labels, key=lambda word: word.confidence))
        chosen.sort(key=lambda word: word.left)


def _has_content(words: list[OCRWord], width: int) -> bool:
    tokens = [re.sub(r"[^\w]", "", word.text) for word in words]
    compact = "".join(tokens)
    if len(compact) > 3 or compact.isdigit():
        return True
    if len(compact) >= 2 and compact.isalpha() and max(word.confidence for word in words) >= 65:
        return True
    return any(speaker_label(word, width) for word in words)
def _trim_page_artifacts(
    words: list[OCRWord],
) -> list[OCRWord]:
    """
    Keep OCR content unchanged.

    Document-specific header/footer removal belongs
    in an optional downstream profile, not in the
    general OCR engine.
    """

    return words


def merge_page_lines(pages: list[OCRPage]) -> OCRPage:
    """Select the most complete OCR candidate independently for each visual line."""
    base = pages[0]
    primary_lines = _candidate_lines(base)
    clusters = [[(0, line)] for line in primary_lines]
    primary_words = [word for line in primary_lines for word in line]
    for source_index, page in enumerate(pages[1:], start=1):
        for line in _candidate_lines(page):
            matches = [
                cluster for cluster in clusters
                if source_index not in {item[0] for item in cluster}
                and _same_physical_line(cluster[0][1], line)
            ]
            if matches:
                closest = min(
                    matches,
                    key=lambda cluster: abs(line_center(cluster[0][1]) - line_center(line)),
                )
                closest.append((source_index, line))
            elif not any(_same_detection(word, primary) for word in line for primary in primary_words):
                clusters.append([(source_index, line)])
    clusters.sort(key=lambda cluster: line_center(cluster[0][1]))
    selected: list[OCRWord] = []
    for line_id, cluster in enumerate(clusters, start=1):
        scored = [(source, line, _line_score(line, base.ocr_width)) for source, line in cluster]
        _, chosen, best_score = max(scored, key=lambda item: item[2])
        primary = next((item for item in scored if item[0] == 0), None)
        if primary and primary[2] >= best_score - 6 and sum(map(len, (word.text for word in primary[1]))) >= sum(map(len, (word.text for word in chosen))) * 0.85:
            _, chosen, _ = primary
        lines = [item[1] for item in cluster]
        _recover_label(chosen, lines, base.ocr_width)
        if _has_content(chosen, base.ocr_width):
            selected.extend(replace(word, block=1, paragraph=order, line=line_id)
                            for order, word in enumerate(chosen, start=1))
    selected = _trim_page_artifacts(selected)
    total = sum(max(1, len(word.text)) for word in selected)
    confidence = sum(word.confidence * max(1, len(word.text)) for word in selected) / max(1, total)
    return OCRPage(
        base.source_path, base.source_width, base.source_height,
        base.ocr_width, base.ocr_height, selected, confidence, -1, "line-ensemble",
    )
