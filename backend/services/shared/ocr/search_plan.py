from __future__ import annotations

from pathlib import Path

from .profile import OCRProfile

SearchSpec = tuple[str, Path, int]


def initial_search_plan(
    quality: str, variants: list[tuple[str, Path]], profile: OCRProfile,
) -> list[SearchSpec]:
    paths = dict(variants)
    psms = tuple(dict.fromkeys((profile.primary_psm, profile.fallback_psm)))
    if quality == "fast":
        return [("normalized", paths["normalized"], profile.primary_psm)]
    if quality == "maximum":
        return [
            (name, paths[name], psm)
            for name in ("normalized", "text-lines", "gentle")
            for psm in psms
        ]
    return [("normalized", paths["normalized"], psm) for psm in psms]


def fallback_search_plan(
    variants: list[tuple[str, Path]], profile: OCRProfile,
) -> list[SearchSpec]:
    paths = dict(variants)
    psms = tuple(dict.fromkeys((profile.primary_psm, profile.fallback_psm)))
    return [
        (name, paths[name], psm)
        for name in ("text-lines", "gentle")
        if name in paths
        for psm in psms
    ]
