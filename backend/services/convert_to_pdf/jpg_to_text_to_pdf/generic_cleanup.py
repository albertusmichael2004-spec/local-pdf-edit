from __future__ import annotations

import re
import unicodedata


_TSV_ROW = re.compile(
    r"^[1-5]\t"
    r"(?:-?\d+(?:\.\d+)?\t){9,}"
)


def clean_ocr_line(
    text: str,
) -> str:
    """
    Normalize OCR formatting without changing vocabulary.

    This function must remain language and
    document independent.
    """

    clean = unicodedata.normalize(
        "NFC",
        text.replace(
            "?",
            "",
        ),
    )

    clean = " ".join(
        part.strip()
        for part in clean.splitlines()
        if (
            part.strip()
            and not _TSV_ROW.match(
                part
            )
        )
    )

    clean = re.sub(
        r"\s+([,.;:!?])",
        r"\1",
        clean,
    )

    clean = re.sub(
        r"([,;:!?])(?=\w)",
        r"\1 ",
        clean,
    )

    clean = re.sub(
        r"[ \t]{2,}",
        " ",
        clean,
    )

    return clean.strip()
