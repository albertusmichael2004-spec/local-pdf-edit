from __future__ import annotations

from pathlib import Path
import shutil

from backend.core.errors import CompressionError
from backend.core.progress import report_fraction, report_progress
from backend.services.shared.compression.ghostscript import profile_from_strength, run_ghostscript
from backend.services.shared.compression.models import CompressionResult, PRESETS
from backend.services.shared.compression.optimizer import optimize_structure
from backend.services.shared.compression.selection import distance_to_range, select_smallest_non_growing


def _try_lossless_candidate(input_path: Path, candidate: Path) -> Path | None:
    """Best-effort structural optimization.

    Compression should not fail just because an optional PyMuPDF optimization
    flag is unavailable in an older existing venv. Ghostscript remains the
    primary lossy compressor for the three quality profiles.
    """
    try:
        optimize_structure(input_path, candidate)
        return candidate if candidate.exists() and candidate.stat().st_size > 0 else None
    except CompressionError:
        candidate.unlink(missing_ok=True)
        return None


def compress_preset(
    input_path: Path,
    output_path: Path,
    mode: str,
    timeout_seconds: int,
) -> CompressionResult:
    if mode not in PRESETS:
        raise CompressionError(f"Unknown compression mode: {mode}")

    original_bytes = input_path.stat().st_size
    workspace = output_path.parent
    gs_candidate = workspace / f"_{mode}_gs.pdf"
    optimized_candidate = workspace / f"_{mode}_optimized.pdf"
    candidates: list[Path] = []
    optimized = _try_lossless_candidate(input_path, optimized_candidate)
    if optimized:
        candidates.append(optimized)

    report_progress("Compressing PDF with Ghostscript", percent=42, detail=mode)
    run_ghostscript(input_path, gs_candidate, PRESETS[mode], timeout_seconds)
    if gs_candidate.exists() and gs_candidate.stat().st_size > 0:
        candidates.append(gs_candidate)

    report_progress("Selecting smallest valid output", percent=92)
    output_bytes, note = select_smallest_non_growing(input_path, candidates, output_path)
    if mode == "extreme" and original_bytes and output_bytes > original_bytes * 0.85:
        note = (
            f"Extreme mode preserved a 150 DPI quality floor and achieved "
            f"{(1 - output_bytes / original_bytes) * 100:.1f}%. "
            "Already-compressed, vector, or text-heavy PDFs may not shrink much without rasterizing pages."
        )
    return CompressionResult(
        output_path=output_path,
        original_bytes=original_bytes,
        output_bytes=output_bytes,
        mode=mode,
        note=note,
    )


def compress_to_target_range(
    input_path: Path,
    output_path: Path,
    target_min_bytes: int,
    target_max_bytes: int,
    timeout_seconds: int,
    max_attempts: int = 9,
) -> CompressionResult:
    if target_min_bytes <= 0 or target_max_bytes <= 0:
        raise CompressionError("Target size values must be greater than zero.")
    if target_min_bytes > target_max_bytes:
        raise CompressionError("Target minimum must not exceed target maximum.")

    original_bytes = input_path.stat().st_size
    if target_min_bytes <= original_bytes <= target_max_bytes:
        shutil.copy2(input_path, output_path)
        return CompressionResult(
            output_path=output_path,
            original_bytes=original_bytes,
            output_bytes=original_bytes,
            mode="custom",
            achieved_target=True,
            target_min_bytes=target_min_bytes,
            target_max_bytes=target_max_bytes,
            note="The original file already falls inside the requested size range.",
        )

    workspace = output_path.parent
    candidates: list[tuple[float, Path, int]] = []
    optimized = workspace / "_custom_optimized.pdf"
    if _try_lossless_candidate(input_path, optimized):
        candidates.append((-0.01, optimized, optimized.stat().st_size))
    cache: dict[float, tuple[Path, int]] = {}

    def evaluate(strength: float) -> tuple[Path, int]:
        key = round(strength, 4)
        if key in cache:
            return cache[key]
        candidate = workspace / f"_custom_{key:.4f}.pdf"
        run_ghostscript(input_path, candidate, profile_from_strength(key), timeout_seconds)
        result = (candidate, candidate.stat().st_size)
        cache[key] = result
        candidates.append((key, candidate, result[1]))
        return result

    report_progress("Testing compression boundaries", percent=28)
    evaluate(0.0)
    evaluate(1.0)
    low, high = 0.0, 1.0
    remaining = max(0, max_attempts - 2)
    for attempt in range(remaining):
        mid = (low + high) / 2
        _, size = evaluate(mid)
        if target_min_bytes <= size <= target_max_bytes:
            high = mid
        elif size > target_max_bytes:
            low = mid
        else:
            high = mid
        report_fraction("Searching target file size", attempt + 1, remaining, 40, 88)

    if not candidates:
        raise CompressionError("No compression candidate could be generated.")

    in_range = [item for item in candidates if target_min_bytes <= item[2] <= target_max_bytes]
    if in_range:
        chosen = min(in_range, key=lambda item: item[0])
        achieved = True
        note = "Target range achieved. Selected the highest-quality candidate within the range."
    else:
        chosen = min(
            candidates,
            key=lambda item: (
                distance_to_range(item[2], target_min_bytes, target_max_bytes),
                item[0],
            ),
        )
        achieved = False
        note = (
            "The requested upper size could not be reached without more destructive processing. "
            "Returning the closest candidate. Vector/text-heavy PDFs may have a hard compression floor."
            if chosen[2] > target_max_bytes
            else "No candidate landed inside the requested range. Returning the closest candidate while favoring higher quality."
        )

    original_distance = distance_to_range(original_bytes, target_min_bytes, target_max_bytes)
    chosen_distance = distance_to_range(chosen[2], target_min_bytes, target_max_bytes)
    if original_distance < chosen_distance:
        shutil.copy2(input_path, output_path)
        chosen_size = original_bytes
        achieved = target_min_bytes <= original_bytes <= target_max_bytes
        note = "The original PDF was closer to the requested target range than generated candidates."
    else:
        shutil.copy2(chosen[1], output_path)
        chosen_size = output_path.stat().st_size

    return CompressionResult(
        output_path=output_path,
        original_bytes=original_bytes,
        output_bytes=chosen_size,
        mode="custom",
        achieved_target=achieved,
        target_min_bytes=target_min_bytes,
        target_max_bytes=target_max_bytes,
        note=note,
    )
