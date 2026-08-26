from __future__ import annotations

from backend.utils.page_ranges import parse_page_selection


def all_or_selection(value: str, total_pages: int) -> set[int] | None:
    if value.strip().lower() == "all":
        return None
    return {page - 1 for page in parse_page_selection(value, total_pages)}
