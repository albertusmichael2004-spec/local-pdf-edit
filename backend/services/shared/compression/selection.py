from __future__ import annotations

from pathlib import Path
import shutil


def select_smallest_non_growing(
    input_path: Path,
    candidates: list[Path],
    final_output: Path,
) -> tuple[int, str]:
    original_size = input_path.stat().st_size
    existing = [path for path in candidates if path.exists() and path.stat().st_size > 0]
    if not existing:
        shutil.copy2(input_path, final_output)
        return original_size, "No compressed candidate could be produced; original copied."

    smallest = min(existing, key=lambda path: path.stat().st_size)
    if smallest.stat().st_size >= original_size:
        shutil.copy2(input_path, final_output)
        return original_size, (
            "The PDF was already efficiently encoded; returning the original avoided file growth."
        )
    shutil.copy2(smallest, final_output)
    return final_output.stat().st_size, ""


def distance_to_range(size: int, minimum: int, maximum: int) -> int:
    if size < minimum:
        return minimum - size
    if size > maximum:
        return size - maximum
    return 0
