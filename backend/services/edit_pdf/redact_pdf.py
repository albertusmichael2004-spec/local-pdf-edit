from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import re
import math
from pathlib import Path
from typing import Any
from uuid import uuid4

import fitz
from PIL import Image, ImageFilter

from backend.core.errors import EditingError
from backend.core.progress import report_fraction, report_progress


SUPPORTED_APPEARANCES = {"black", "white", "blur", "pixelate"}
MAX_REDACTION_MARKS = 2_000


@dataclass(frozen=True)
class RedactionResult:
    marks_applied: int
    pages_redacted: int
    text_regions_clear: int
    verified: bool

    def public(self) -> dict[str, object]:
        return {
            "marks_applied": self.marks_applied,
            "pages_redacted": self.pages_redacted,
            "text_regions_clear": self.text_regions_clear,
            "verified": self.verified,
        }


@dataclass(frozen=True)
class _ResolvedMark:
    mark_id: str
    page_index: int
    rect: fitz.Rect
    appearance: str
    color: tuple[float, float, float]


def _hex_color(value: str, fallback: str = "#000000") -> tuple[float, float, float]:
    color = str(value or fallback).strip().lstrip("#")
    if len(color) == 3:
        color = "".join(character * 2 for character in color)
    if len(color) != 6:
        raise EditingError("Redaction color must be a 3- or 6-digit hex value.")
    try:
        channels = tuple(int(color[index:index + 2], 16) / 255 for index in (0, 2, 4))
    except ValueError as exc:
        raise EditingError("Redaction color must be a valid hex value.") from exc
    return channels


def _page_index(mark: dict[str, Any], page_ids: list[str], page_count: int) -> int:
    page_instance_id = str(mark.get("page_instance_id") or "").strip()
    if page_instance_id:
        try:
            return page_ids.index(page_instance_id)
        except ValueError as exc:
            raise EditingError(
                "A redaction mark belongs to an older page arrangement. Re-open the page and mark it again."
            ) from exc
    try:
        page_number = int(mark.get("page_number"))
    except (TypeError, ValueError) as exc:
        raise EditingError("Every redaction mark must identify a page.") from exc
    if page_number < 1 or page_number > page_count:
        raise EditingError(f"Redaction page {page_number} is outside 1-{page_count}.")
    return page_number - 1


def _normalized_rect(mark: dict[str, Any], page: fitz.Page) -> fitz.Rect:
    payload = mark.get("rect")
    if not isinstance(payload, dict) or payload.get("space", "normalized_view") != "normalized_view":
        raise EditingError("Redaction rectangles must use normalized_view coordinates.")
    try:
        values = [float(payload[key]) for key in ("x0", "y0", "x1", "y1")]
    except (KeyError, TypeError, ValueError) as exc:
        raise EditingError("A redaction rectangle is missing valid coordinates.") from exc
    if not all(math.isfinite(value) for value in values):
        raise EditingError("Redaction rectangle coordinates must be finite numbers.")
    x0, y0, x1, y1 = values
    x0, x1 = sorted((max(0.0, min(1.0, x0)), max(0.0, min(1.0, x1))))
    y0, y1 = sorted((max(0.0, min(1.0, y0)), max(0.0, min(1.0, y1))))
    if x1 - x0 < 0.001 or y1 - y0 < 0.001:
        raise EditingError("Redaction rectangles must cover a visible area.")

    # Browser previews are rendered in the page's visible (rotated) coordinate
    # space. PyMuPDF redaction annotations use the unrotated PDF page space.
    visible = page.rect
    view_rect = fitz.Rect(
        visible.x0 + x0 * visible.width,
        visible.y0 + y0 * visible.height,
        visible.x0 + x1 * visible.width,
        visible.y0 + y1 * visible.height,
    )
    unrotated = view_rect * page.derotation_matrix
    unrotated.normalize()
    return unrotated


def _resolve_marks(
    document: fitz.Document,
    marks: list[dict[str, Any]],
    page_ids: list[str],
    appearance: str,
    color: str,
) -> list[_ResolvedMark]:
    if not marks:
        raise EditingError("Add at least one redaction mark before applying redaction.")
    if len(marks) > MAX_REDACTION_MARKS:
        raise EditingError(f"A maximum of {MAX_REDACTION_MARKS} redaction marks can run at once.")
    if len(page_ids) != document.page_count or len(set(page_ids)) != document.page_count:
        raise EditingError("The workflow page identity map is invalid.")
    default_appearance = str(appearance or "black").lower()
    if default_appearance not in SUPPORTED_APPEARANCES:
        raise EditingError(f"Unknown redaction appearance: {default_appearance}")
    default_color = _hex_color(color, "#000000")

    resolved: list[_ResolvedMark] = []
    for index, mark in enumerate(marks, start=1):
        if not isinstance(mark, dict):
            raise EditingError(f"Redaction mark {index} must be an object.")
        page_index = _page_index(mark, page_ids, document.page_count)
        page = document[page_index]
        mark_appearance = str(mark.get("appearance", {}).get("mode") or default_appearance).lower()
        if mark_appearance not in SUPPORTED_APPEARANCES:
            raise EditingError(f"Unknown redaction appearance: {mark_appearance}")
        raw_color = mark.get("appearance", {}).get("color") or color
        mark_color = _hex_color(raw_color, "#000000") if mark_appearance == "black" else default_color
        resolved.append(_ResolvedMark(
            mark_id=str(mark.get("mark_id") or f"mark_{index}"),
            page_index=page_index,
            rect=_normalized_rect(mark, page),
            appearance=mark_appearance,
            color=mark_color,
        ))
    return resolved


def _transformed_clip(page: fitz.Page, rect: fitz.Rect, mode: str) -> bytes:
    pixmap = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), clip=rect, alpha=False)
    with Image.open(BytesIO(pixmap.tobytes("png"))) as source:
        image = source.convert("RGB")
        if mode == "blur":
            transformed = image.filter(ImageFilter.GaussianBlur(radius=max(5, min(image.size) / 18)))
        else:
            block_width = max(1, image.width // max(6, min(28, image.width // 7 or 6)))
            block_height = max(1, image.height // max(6, min(28, image.height // 7 or 6)))
            transformed = image.resize((block_width, block_height), Image.Resampling.BOX).resize(
                image.size,
                Image.Resampling.NEAREST,
            )
        stream = BytesIO()
        transformed.save(stream, format="PNG", optimize=True)
        return stream.getvalue()


def _contains_text_character_center(page: fitz.Page, rect: fitz.Rect) -> bool:
    """Avoid false failures from clip extraction returning an adjacent whole word."""
    raw = page.get_text("rawdict")
    for block in raw.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                for character in span.get("chars", []):
                    bounds = fitz.Rect(character.get("bbox", (0, 0, 0, 0)))
                    center = fitz.Point((bounds.x0 + bounds.x1) / 2, (bounds.y0 + bounds.y1) / 2)
                    if rect.contains(center):
                        return True
    return False


def redact_pdf(
    input_path: Path,
    output_path: Path,
    marks: list[dict[str, Any]],
    page_ids: list[str],
    appearance: str = "black",
    color: str = "#000000",
) -> RedactionResult:
    """Securely remove marked text, image pixels, and intersecting vector art."""
    try:
        report_progress("Resolving secure redaction marks", percent=16)
        with fitz.open(input_path) as document:
            if document.needs_pass:
                raise EditingError("Encrypted PDF. Unlock it before redacting content.")
            resolved = _resolve_marks(document, marks, page_ids, appearance, color)
            by_page: dict[int, list[_ResolvedMark]] = {}
            for mark in resolved:
                by_page.setdefault(mark.page_index, []).append(mark)

            for completed, (page_index, page_marks) in enumerate(sorted(by_page.items()), start=1):
                page = document[page_index]
                replacement_streams: list[tuple[fitz.Rect, bytes]] = []
                for mark in page_marks:
                    if mark.appearance in {"blur", "pixelate"}:
                        replacement_streams.append((mark.rect, _transformed_clip(page, mark.rect, mark.appearance)))
                    fill = mark.color if mark.appearance == "black" else (1.0, 1.0, 1.0)
                    page.add_redact_annot(mark.rect, fill=fill, cross_out=False)

                page.apply_redactions(
                    images=fitz.PDF_REDACT_IMAGE_PIXELS,
                    graphics=fitz.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED,
                    text=fitz.PDF_REDACT_TEXT_REMOVE,
                )
                for rect, stream in replacement_streams:
                    page.insert_image(rect, stream=stream, overlay=True, keep_proportion=False)
                report_fraction("Removing marked PDF content", completed, len(by_page), 24, 78)

            report_progress("Saving sanitized PDF", percent=84)
            document.save(output_path, garbage=4, clean=True, deflate=True, incremental=False)

        report_progress("Verifying redacted regions", percent=92)
        clear_regions = 0
        with fitz.open(output_path) as verified_document:
            for mark in resolved:
                page = verified_document[mark.page_index]
                # Text extraction with ``clip=`` can return a whole adjacent
                # word that only grazes the rectangle. Character centers give
                # us the same visible-area contract used by the editor.
                if not _contains_text_character_center(page, mark.rect):
                    clear_regions += 1
        verified = clear_regions == len(resolved)
        if not verified:
            output_path.unlink(missing_ok=True)
            raise EditingError("Redaction verification failed because text still intersects a marked region.")
        return RedactionResult(
            marks_applied=len(resolved),
            pages_redacted=len(by_page),
            text_regions_clear=clear_regions,
            verified=True,
        )
    except EditingError:
        raise
    except Exception as exc:
        output_path.unlink(missing_ok=True)
        raise EditingError(f"Redact PDF failed: {exc}") from exc


def search_redaction_text(
    input_path: Path,
    query: str,
    page_ids: list[str],
    *,
    exact: bool = False,
    max_matches: int = 500,
) -> list[dict[str, object]]:
    needle = str(query or "").strip()
    if not needle:
        raise EditingError("Enter text to find and redact.")
    if len(needle) > 500:
        raise EditingError("Search text must be 500 characters or fewer.")
    try:
        results: list[dict[str, object]] = []
        with fitz.open(input_path) as document:
            if document.needs_pass:
                raise EditingError("Encrypted PDF. Unlock it before searching.")
            if len(page_ids) != document.page_count:
                raise EditingError("The workflow page identity map is invalid.")
            for page_index, page in enumerate(document):
                visible = page.rect
                words = page.get_text("words") if exact else []
                for match in page.search_for(needle):
                    if exact and not _is_exact_text_match(match, words, needle):
                        continue
                    view_rect = match * page.rotation_matrix
                    view_rect.normalize()
                    results.append({
                        "mark_id": f"search_{uuid4().hex}",
                        "page_instance_id": page_ids[page_index],
                        "page_number": page_index + 1,
                        "rect": {
                            "space": "normalized_view",
                            "x0": max(0.0, min(1.0, (view_rect.x0 - visible.x0) / max(1.0, visible.width))),
                            "y0": max(0.0, min(1.0, (view_rect.y0 - visible.y0) / max(1.0, visible.height))),
                            "x1": max(0.0, min(1.0, (view_rect.x1 - visible.x0) / max(1.0, visible.width))),
                            "y1": max(0.0, min(1.0, (view_rect.y1 - visible.y0) / max(1.0, visible.height))),
                        },
                        "source": "search",
                        "search_text": needle,
                    })
                    if len(results) >= max_matches:
                        return results
        return results
    except EditingError:
        raise
    except Exception as exc:
        raise EditingError(f"Text search failed: {exc}") from exc


def select_redaction_text(
    input_path: Path,
    page_ids: list[str],
    page_number: int,
    page_instance_id: str,
    selection: dict[str, Any],
    *,
    max_matches: int = 500,
) -> list[dict[str, object]]:
    """Resolve a dragged preview selection to real character runs in the PDF text layer."""
    try:
        with fitz.open(input_path) as document:
            if document.needs_pass:
                raise EditingError("Encrypted PDF. Unlock it before selecting text.")
            if len(page_ids) != document.page_count:
                raise EditingError("The workflow page identity map is invalid.")
            mark = {
                "page_number": page_number,
                "page_instance_id": page_instance_id,
                "rect": selection,
            }
            page_index = _page_index(mark, page_ids, document.page_count)
            page = document[page_index]
            selection_rect = _normalized_rect(mark, page)
            visible = page.rect
            results: list[dict[str, object]] = []

            def append_run(characters: list[dict[str, Any]]) -> None:
                if not characters or len(results) >= max_matches:
                    return
                label = "".join(str(character.get("c", "")) for character in characters).strip()
                if not label:
                    return
                bounds = fitz.Rect(characters[0].get("bbox", (0, 0, 0, 0)))
                for character in characters[1:]:
                    bounds |= fitz.Rect(character.get("bbox", (0, 0, 0, 0)))
                view_rect = bounds * page.rotation_matrix
                view_rect.normalize()
                results.append({
                    "mark_id": f"text_select_{uuid4().hex}",
                    "page_instance_id": page_ids[page_index],
                    "page_number": page_index + 1,
                    "rect": {
                        "space": "normalized_view",
                        "x0": max(0.0, min(1.0, (view_rect.x0 - visible.x0) / max(1.0, visible.width))),
                        "y0": max(0.0, min(1.0, (view_rect.y0 - visible.y0) / max(1.0, visible.height))),
                        "x1": max(0.0, min(1.0, (view_rect.x1 - visible.x0) / max(1.0, visible.width))),
                        "y1": max(0.0, min(1.0, (view_rect.y1 - visible.y0) / max(1.0, visible.height))),
                    },
                    "source": "text_selection",
                    "search_text": label,
                })

            raw = page.get_text("rawdict")
            for block in raw.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        run: list[dict[str, Any]] = []
                        for character in span.get("chars", []):
                            bounds = fitz.Rect(character.get("bbox", (0, 0, 0, 0)))
                            center = fitz.Point(
                                (bounds.x0 + bounds.x1) / 2,
                                (bounds.y0 + bounds.y1) / 2,
                            )
                            if selection_rect.contains(center):
                                run.append(character)
                            else:
                                append_run(run)
                                run = []
                        append_run(run)
                        if len(results) >= max_matches:
                            return results
            return results
    except EditingError:
        raise
    except Exception as exc:
        raise EditingError(f"Text selection failed: {exc}") from exc


def _is_exact_text_match(
    match: fitz.Rect,
    words: list[tuple[object, ...]],
    needle: str,
) -> bool:
    """Reject substring hits while keeping punctuation-delimited words/phrases."""
    matched_words: list[tuple[int, int, int, str]] = []
    for word in words:
        word_rect = fitz.Rect(float(word[0]), float(word[1]), float(word[2]), float(word[3]))
        intersection = word_rect & match
        if intersection.is_empty or intersection.get_area() <= 0:
            continue
        matched_words.append((int(word[5]), int(word[6]), int(word[7]), str(word[4])))
    if not matched_words:
        return False
    matched_words.sort(key=lambda item: (item[0], item[1], item[2]))
    candidate = " ".join(item[3] for item in matched_words)

    def normalized(value: str) -> str:
        collapsed = " ".join(value.split()).casefold()
        return re.sub(r"^\W+|\W+$", "", collapsed, flags=re.UNICODE)

    return normalized(candidate) == normalized(needle)
