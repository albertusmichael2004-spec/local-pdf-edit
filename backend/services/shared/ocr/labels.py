from __future__ import annotations

import re

from .models import OCRWord

_P_LABELS = {"p", "pi", "pp", "ps"}
_U_LABELS = {"u", "uu", "uv", "v", "cv"}
_PU_LABELS = {"pu", "p+u", "p#u"}


def speaker_label(word: OCRWord, page_width: int) -> str | None:
    if word.left > page_width * 0.28:
        return None
    token = re.sub(r"[^a-z+#]", "", word.text.lower())
    if token in _P_LABELS:
        return "P:"
    if token in _U_LABELS:
        return "U:"
    if token in _PU_LABELS:
        return "P+U:"
    return None
