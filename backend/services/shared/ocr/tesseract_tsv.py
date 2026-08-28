from __future__ import annotations

import subprocess
from pathlib import Path

from backend.core.errors import OCRError
from backend.core.subprocesses import run_hidden

from .models import OCRWord

TSV_COLUMNS = (
    "level", "page_num", "block_num", "par_num", "line_num", "word_num",
    "left", "top", "width", "height", "conf", "text",
)


def _literal_tsv_rows(output: str) -> list[dict[str, str]]:
    """Parse Tesseract TSV without treating OCR quote marks as CSV syntax."""
    lines = output.splitlines()
    if not lines or tuple(lines[0].split("\t")) != TSV_COLUMNS:
        raise OCRError("Tesseract returned malformed TSV output.")
    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        values = line.split("\t", len(TSV_COLUMNS) - 1)
        if len(values) == len(TSV_COLUMNS):
            rows.append(dict(zip(TSV_COLUMNS, values, strict=True)))
    return rows


def run_tsv(
    image_path: Path,
    tesseract_executable: str,
    language: str,
    psm: int,
    tessdata_dir: Path | None = None,
) -> tuple[list[OCRWord], float]:
    command = [tesseract_executable, str(image_path), "stdout"]
    if tessdata_dir:
        command += ["--tessdata-dir", str(tessdata_dir)]
    command += [
        "-l", language, "--oem", "1", "--psm", str(psm),
        "-c", "tessedit_create_tsv=1", "-c", "tessedit_create_txt=0",
    ]
    try:
        result = run_hidden(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=240,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise OCRError("Tesseract OCR timed out.") from exc
    except OSError as exc:
        raise OCRError(f"Tesseract failed to start: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr or result.stdout or "Unknown Tesseract error."
        raise OCRError(f"Tesseract OCR failed: {detail[-1200:]}")
    words: list[OCRWord] = []
    weighted_confidence = 0.0
    total_weight = 0
    for row in _literal_tsv_rows(result.stdout):
        if row.get("level") != "5" or not (row.get("text") or "").strip():
            continue
        try:
            confidence = float(row.get("conf", "-1"))
            geometry = [int(row[key]) for key in ("left", "top", "width", "height")]
            hierarchy = [int(row[key]) for key in ("block_num", "par_num", "line_num")]
        except (TypeError, ValueError):
            continue
        if confidence < 0:
            continue
        text = row["text"].strip()
        words.append(OCRWord(
            text=text,
            confidence=confidence,
            left=geometry[0],
            top=geometry[1],
            width=geometry[2],
            height=geometry[3],
            block=hierarchy[0],
            paragraph=hierarchy[1],
            line=hierarchy[2],
        ))
        weight = max(1, len(text))
        total_weight += weight
        weighted_confidence += confidence * weight
    return words, weighted_confidence / total_weight if total_weight else 0.0
