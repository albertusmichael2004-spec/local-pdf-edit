from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )

import argparse
import csv
import json
import re
import statistics
import tempfile
import time
import unicodedata


from docx import Document

from backend.services.convert_to_pdf.jpg_to_text_to_pdf import (
    jpg_to_text_to_pdf_or_word,
)


SUPPORTED_IMAGES = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
}


def normalize_text(
    text: str,
    *,
    ignore_case: bool,
) -> str:
    text = unicodedata.normalize(
        "NFC",
        text,
    )

    text = (
        text
        .replace(
            "\r\n",
            "\n",
        )
        .replace(
            "\r",
            "\n",
        )
    )

    lines = [
        re.sub(
            r"[ \t]+",
            " ",
            line,
        ).strip()
        for line
        in text.splitlines()
    ]

    text = "\n".join(
        line
        for line in lines
        if line
    )

    if ignore_case:
        text = text.casefold()

    return text.strip()


def levenshtein(
    source: list[str],
    target: list[str],
) -> int:
    if not source:
        return len(target)

    if not target:
        return len(source)

    previous = list(
        range(
            len(target) + 1
        )
    )

    for source_index, source_item in enumerate(
        source,
        start=1,
    ):
        current = [
            source_index
        ]

        for target_index, target_item in enumerate(
            target,
            start=1,
        ):
            insertion = (
                current[
                    target_index - 1
                ]
                + 1
            )

            deletion = (
                previous[
                    target_index
                ]
                + 1
            )

            substitution = (
                previous[
                    target_index - 1
                ]
                + (
                    source_item
                    != target_item
                )
            )

            current.append(
                min(
                    insertion,
                    deletion,
                    substitution,
                )
            )

        previous = current

    return previous[-1]


def character_error_rate(
    truth: str,
    prediction: str,
) -> float:
    distance = levenshtein(
        list(truth),
        list(prediction),
    )

    return (
        distance
        / max(
            1,
            len(truth),
        )
    )


def word_error_rate(
    truth: str,
    prediction: str,
) -> float:
    truth_words = (
        truth.split()
    )

    prediction_words = (
        prediction.split()
    )

    distance = levenshtein(
        truth_words,
        prediction_words,
    )

    return (
        distance
        / max(
            1,
            len(truth_words),
        )
    )


def duplicate_line_ratio(
    text: str,
) -> float:
    lines = [
        re.sub(
            r"\s+",
            " ",
            line,
        )
        .strip()
        .casefold()
        for line
        in text.splitlines()
        if line.strip()
    ]

    if not lines:
        return 0.0

    duplicate_count = (
        len(lines)
        - len(set(lines))
    )

    return (
        duplicate_count
        / len(lines)
    )


def suspicious_token_ratio(
    text: str,
) -> float:
    """
    Generic anomaly detector.

    Does not use a dictionary and does not
    assume any specific language.
    """

    tokens = re.findall(
        r"\S+",
        text,
        flags=re.UNICODE,
    )

    if not tokens:
        return 0.0

    suspicious = 0

    for token in tokens:
        characters = [
            character
            for character
            in token
            if not character.isspace()
        ]

        if not characters:
            continue

        alphanumeric = sum(
            character.isalnum()
            for character
            in characters
        )

        controls = sum(
            unicodedata
            .category(character)
            .startswith("C")
            for character
            in characters
        )

        unusual_symbols = sum(
            (
                not character.isalnum()
                and not character.isspace()
                and character
                not in (
                    ".,;:!?()[]{}"
                    "\"'????-??/+&#%@"
                )
            )
            for character
            in characters
        )

        alphanumeric_ratio = (
            alphanumeric
            / len(characters)
        )

        if (
            controls > 0
            or (
                len(characters) >= 4
                and alphanumeric_ratio
                < 0.35
            )
            or (
                unusual_symbols
                >= max(
                    2,
                    len(characters) // 2,
                )
            )
        ):
            suspicious += 1

    return (
        suspicious
        / len(tokens)
    )


def read_docx_text(
    path: Path,
) -> str:
    document = Document(
        path
    )

    return "\n".join(
        paragraph.text
        for paragraph
        in document.paragraphs
    )


def discover_cases(
    images_dir: Path,
    truth_dir: Path,
) -> list[tuple[Path, Path]]:
    cases: list[
        tuple[Path, Path]
    ] = []

    for image_path in sorted(
        images_dir.iterdir()
    ):
        if (
            not image_path.is_file()
            or image_path.suffix.lower()
            not in SUPPORTED_IMAGES
        ):
            continue

        truth_path = (
            truth_dir
            / (
                image_path.stem
                + ".txt"
            )
        )

        if truth_path.exists():
            cases.append(
                (
                    image_path,
                    truth_path,
                )
            )

    return cases


def run_case(
    image_path: Path,
    truth_path: Path,
    *,
    language: str,
    quality: str,
    ignore_case: bool,
) -> dict[str, object]:
    truth = normalize_text(
        truth_path.read_text(
            encoding="utf-8",
        ),
        ignore_case=ignore_case,
    )

    if not truth:
        raise ValueError(
            "Ground-truth file is empty after normalization: "
            f"{truth_path}"
        )

    with tempfile.TemporaryDirectory(
        prefix=(
            "pdfwb-ocr-training-"
        )
    ) as temp:
        output = (
            Path(temp)
            / "ocr.docx"
        )

        started = (
            time.perf_counter()
        )

        count = (
            jpg_to_text_to_pdf_or_word(
                image_paths=[
                    image_path
                ],
                output_path=output,
                output_format="docx",
                language=language,
                quality=quality,
                layout_mode="editable",
            )
        )

        runtime = (
            time.perf_counter()
            - started
        )

        if count != 1:
            raise RuntimeError(
                f"OCR returned "
                f"{count} pages for "
                f"{image_path.name}."
            )

        prediction = (
            normalize_text(
                read_docx_text(
                    output
                ),
                ignore_case=ignore_case,
            )
        )

    return {
        "file":
            image_path.name,

        "language":
            language,

        "quality":
            quality,

        "cer":
            character_error_rate(
                truth,
                prediction,
            ),

        "wer":
            word_error_rate(
                truth,
                prediction,
            ),

        "duplicate_line_ratio":
            duplicate_line_ratio(
                prediction
            ),

        "suspicious_token_ratio":
            suspicious_token_ratio(
                prediction
            ),

        "runtime_seconds":
            runtime,

        "truth_characters":
            len(truth),

        "ocr_characters":
            len(prediction),

        "truth_words":
            len(
                truth.split()
            ),

        "ocr_words":
            len(
                prediction.split()
            ),

        "prediction":
            prediction,
    }


def mean_metric(
    rows: list[
        dict[str, object]
    ],
    key: str,
) -> float:
    values = [
        float(
            row[key]
        )
        for row in rows
    ]

    if not values:
        return 0.0

    return (
        statistics.mean(
            values
        )
    )


def write_csv(
    path: Path,
    rows: list[
        dict[str, object]
    ],
) -> None:
    fields = [
        "file",
        "language",
        "quality",
        "cer",
        "wer",
        "duplicate_line_ratio",
        "suspicious_token_ratio",
        "runtime_seconds",
        "truth_characters",
        "ocr_characters",
        "truth_words",
        "ocr_words",
    ]

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = (
            csv.DictWriter(
                handle,
                fieldnames=fields,
            )
        )

        writer.writeheader()

        for row in rows:
            writer.writerow(
                {
                    field:
                        row[field]
                    for field
                    in fields
                }
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate Local PDF Workbench "
            "OCR against local ground truth."
        )
    )

    parser.add_argument(
        "--images",
        type=Path,
        default=Path(
            "training/ocr/"
            "private/images"
        ),
    )

    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=Path(
            "training/ocr/"
            "private/ground_truth"
        ),
    )

    parser.add_argument(
        "--results",
        type=Path,
        default=Path(
            "training/ocr/results"
        ),
    )

    parser.add_argument(
        "--language",
        default="eng",
    )

    parser.add_argument(
        "--quality",
        choices=[
            "fast",
            "accurate",
            "maximum",
        ],
        default="accurate",
    )

    parser.add_argument(
        "--ignore-case",
        action="store_true",
    )

    args = parser.parse_args()

    cases = discover_cases(
        args.images,
        args.ground_truth,
    )

    if not cases:
        raise SystemExit(
            "No training/evaluation cases "
            "found. Image and ground-truth "
            ".txt files must have matching "
            "filenames."
        )

    args.results.mkdir(
        parents=True,
        exist_ok=True,
    )

    rows: list[
        dict[str, object]
    ] = []

    print(
        f"Running {len(cases)} "
        "OCR evaluation case(s)..."
    )

    for index, (
        image_path,
        truth_path,
    ) in enumerate(
        cases,
        start=1,
    ):
        print(
            f"[{index}/{len(cases)}] "
            f"{image_path.name}"
        )

        row = run_case(
            image_path,
            truth_path,
            language=args.language,
            quality=args.quality,
            ignore_case=args.ignore_case,
        )

        rows.append(
            row
        )

        print(
            "  CER="
            f"{row['cer']:.4f}"
            "  WER="
            f"{row['wer']:.4f}"
            "  runtime="
            f"{row['runtime_seconds']:.2f}s"
        )

    csv_path = (
        args.results
        / (
            f"ocr_{args.quality}_"
            f"{args.language}.csv"
        )
    )

    json_path = (
        args.results
        / (
            f"ocr_{args.quality}_"
            f"{args.language}.json"
        )
    )

    write_csv(
        csv_path,
        rows,
    )

    summary = {
        "cases":
            len(rows),

        "quality":
            args.quality,

        "language":
            args.language,

        "mean_cer":
            mean_metric(
                rows,
                "cer",
            ),

        "mean_wer":
            mean_metric(
                rows,
                "wer",
            ),

        "mean_duplicate_line_ratio":
            mean_metric(
                rows,
                "duplicate_line_ratio",
            ),

        "mean_suspicious_token_ratio":
            mean_metric(
                rows,
                "suspicious_token_ratio",
            ),

        "mean_runtime_seconds":
            mean_metric(
                rows,
                "runtime_seconds",
            ),

        "rows":
            rows,
    }

    json_path.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print(
        "=== OCR EVALUATION SUMMARY ==="
    )

    print(
        f"Cases        : "
        f"{summary['cases']}"
    )

    print(
        f"Mean CER     : "
        f"{summary['mean_cer']:.4f}"
    )

    print(
        f"Mean WER     : "
        f"{summary['mean_wer']:.4f}"
    )

    print(
        "Duplicate    : "
        f"{summary['mean_duplicate_line_ratio']:.4f}"
    )

    print(
        "Suspicious   : "
        f"{summary['mean_suspicious_token_ratio']:.4f}"
    )

    print(
        f"Runtime/page : "
        f"{summary['mean_runtime_seconds']:.2f}s"
    )

    print(
        f"CSV          : "
        f"{csv_path}"
    )

    print(
        f"JSON         : "
        f"{json_path}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
