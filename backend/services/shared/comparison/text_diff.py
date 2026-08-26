from __future__ import annotations

from difflib import SequenceMatcher
import re

def operation_counts(a: list[str] | str, b: list[str] | str) -> tuple[int, int, int, list[dict]]:
    matcher = SequenceMatcher(None, a, b, autojunk=False)
    inserted = deleted = replaced = 0
    preview: list[dict] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        left_count = i2 - i1
        right_count = j2 - j1
        if tag == "insert":
            inserted += right_count
        elif tag == "delete":
            deleted += left_count
        elif tag == "replace":
            common = min(left_count, right_count)
            replaced += common
            deleted += max(0, left_count - right_count)
            inserted += max(0, right_count - left_count)
        if len(preview) < 12:
            if isinstance(a, str):
                left_val = a[i1:i2]
                right_val = b[j1:j2]
            else:
                left_val = " ".join(a[i1:i2])
                right_val = " ".join(b[j1:j2])
            preview.append({
                "type": tag,
                "left": left_val[:280],
                "right": right_val[:280],
                "left_index": i1,
                "right_index": j1,
            })
    return inserted, deleted, replaced, preview

def tokenize_words(text: str) -> list[str]:
    # Exact word order comparison. Punctuation remains attached to each token,
    # so punctuation changes also register as word-sequence differences.
    return re.findall(r"\S+", text, flags=re.UNICODE)
