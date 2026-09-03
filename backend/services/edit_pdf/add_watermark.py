from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import uuid

import fitz

from backend.core.errors import EditingError
from backend.core.progress import report_fraction, report_progress
from backend.services.edit_pdf.watermark_fonts import resolve_font


@dataclass(frozen=True)
class WatermarkRule:
    text: str
    pages_zero_based: set[int] | None
    opacity: float = 0.22
    font_size: float = 42
    rotation: int = 45
    font_key: str = "arial"


def _font_for_page(page: fitz.Page, font_key: str):
    spec = resolve_font(font_key)
    if spec.file_path:
        alias = f"wm_{uuid.uuid4().hex[:10]}"
        page.insert_font(fontname=alias, fontfile=str(spec.file_path))
        metrics = fitz.Font(fontfile=str(spec.file_path))
        return alias, metrics
    builtin = spec.builtin_name or "helv"
    return builtin, fitz.Font(fontname=builtin)


def _insert_rule(page: fitz.Page, rule: WatermarkRule) -> None:
    text = rule.text.strip()
    if not text:
        raise EditingError("Watermark text cannot be empty.")
    opacity = min(1.0, max(0.05, float(rule.opacity)))
    font_size = min(180.0, max(8.0, float(rule.font_size)))
    rotation = int(rule.rotation) % 360
    font_name, font_metrics = _font_for_page(page, rule.font_key)
    center = fitz.Point(page.rect.width / 2, page.rect.height / 2)
    text_width = font_metrics.text_length(text, fontsize=font_size)
    start = fitz.Point(center.x - text_width / 2, center.y)

    kwargs = dict(
        fontname=font_name,
        fontsize=font_size,
        fill_opacity=opacity,
        overlay=True,
    )
    if rotation == 0:
        page.insert_text(start, text, **kwargs)
    else:
        matrix = fitz.Matrix(1, 1).prerotate(rotation)
        page.insert_text(start, text, morph=(center, matrix), **kwargs)


def add_text_watermarks(
    input_path: Path,
    output_path: Path,
    rules: Iterable[WatermarkRule],
) -> int:
    rules = list(rules)
    if not rules:
        raise EditingError("Add at least one watermark before exporting the PDF.")
    try:
        with fitz.open(input_path) as doc:
            if doc.needs_pass:
                raise EditingError("Encrypted PDF. Unlock it before editing.")
            report_progress("Preparing watermark rules", percent=22, detail=f"{len(rules)} rule(s)")
            for index, page in enumerate(doc):
                for rule in rules:
                    if rule.pages_zero_based is not None and index not in rule.pages_zero_based:
                        continue
                    _insert_rule(page, rule)
                report_fraction("Applying watermark to pages", index + 1, doc.page_count, 25, 88)
            report_progress("Saving watermarked PDF", percent=92)
            doc.save(output_path, garbage=4, deflate=True)
            return doc.page_count
    except EditingError:
        raise
    except Exception as exc:
        raise EditingError(f"Watermark failed: {exc}") from exc


def add_text_watermark(
    input_path: Path,
    output_path: Path,
    text: str,
    pages_zero_based: set[int] | None,
    opacity: float = 0.22,
    font_size: float = 42,
    rotation: int = 45,
    font_key: str = "arial",
) -> int:
    """Backward-compatible single-watermark entry point."""
    return add_text_watermarks(
        input_path,
        output_path,
        [
            WatermarkRule(
                text=text,
                pages_zero_based=pages_zero_based,
                opacity=opacity,
                font_size=font_size,
                rotation=rotation,
                font_key=font_key,
            )
        ],
    )
