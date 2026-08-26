from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PageGroup:
    label: str
    pages_zero_based: tuple[int, ...]


def _parse_page_token(token: str, total_pages: int) -> list[int]:
    token = token.strip()
    if not token:
        return []

    if "-" in token:
        parts = [part.strip() for part in token.split("-", 1)]
        if len(parts) != 2 or not all(parts):
            raise ValueError(f"Invalid page range: '{token}'.")
        try:
            start, end = int(parts[0]), int(parts[1])
        except ValueError as exc:
            raise ValueError(f"Invalid page range: '{token}'.") from exc
        if start > end:
            raise ValueError(f"Range start must be <= end: '{token}'.")
        pages = list(range(start, end + 1))
    else:
        try:
            pages = [int(token)]
        except ValueError as exc:
            raise ValueError(f"Invalid page number: '{token}'.") from exc

    for page in pages:
        if page < 1 or page > total_pages:
            raise ValueError(
                f"Page {page} is outside this PDF's 1-{total_pages} page range."
            )
    return pages


def parse_page_selection(expression: str, total_pages: int) -> list[int]:
    """Parse a comma-separated page selection into 1-based pages.

    Examples: ``1,3,5-8`` or ``8-10,2``. Order and duplicates are preserved so
    the same parser can also drive the Organize PDF feature.
    """
    expression = expression.strip()
    if not expression:
        raise ValueError("Enter at least one page number or range.")

    pages: list[int] = []
    for token in expression.split(","):
        pages.extend(_parse_page_token(token, total_pages))
    if not pages:
        raise ValueError("Enter at least one valid page.")
    return pages


def parse_group_expression(expression: str, total_pages: int) -> list[PageGroup]:
    """Parse split groups.

    Semicolons separate output files. Commas combine pages in one output file.
    Example: ``1-3;4,6,8-10`` creates two PDFs.
    """
    expression = expression.strip()
    if not expression:
        raise ValueError("Enter at least one page range.")

    groups: list[PageGroup] = []
    for index, group_text in enumerate(expression.split(";"), start=1):
        group_text = group_text.strip()
        if not group_text:
            continue

        one_based_pages = parse_page_selection(group_text, total_pages)
        groups.append(
            PageGroup(
                label=group_text,
                pages_zero_based=tuple(page - 1 for page in one_based_pages),
            )
        )

    if not groups:
        raise ValueError("Enter at least one valid split group.")
    return groups


def groups_every_page(total_pages: int) -> list[PageGroup]:
    return [
        PageGroup(label=str(page), pages_zero_based=(page - 1,))
        for page in range(1, total_pages + 1)
    ]


def groups_every_n_pages(total_pages: int, n: int) -> list[PageGroup]:
    if n < 1:
        raise ValueError("Pages per file must be at least 1.")

    groups: list[PageGroup] = []
    for start in range(1, total_pages + 1, n):
        end = min(total_pages, start + n - 1)
        groups.append(
            PageGroup(
                label=f"{start}-{end}" if start != end else str(start),
                pages_zero_based=tuple(range(start - 1, end)),
            )
        )
    return groups
