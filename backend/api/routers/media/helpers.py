from __future__ import annotations

from pathlib import Path

from fastapi import UploadFile

from backend.api.workspace import RequestWorkspace
from backend.services.media.models import MediaSource


async def save_sources(workspace: RequestWorkspace, files: list[UploadFile]) -> list[MediaSource]:
    sources = []
    for index, upload in enumerate(files, start=1):
        path, name, _ = await workspace.save_media_file(upload, f"media_{index}", f"{index:04d}_")
        sources.append(MediaSource(path, name))
    return sources


def output_headers(source_bytes: int, output_bytes: int, warnings: tuple[str, ...]) -> dict[str, str]:
    reduction = 0.0 if not source_bytes else (source_bytes - output_bytes) * 100 / source_bytes
    headers = {
        "X-Original-Bytes": str(source_bytes),
        "X-Output-Bytes": str(output_bytes),
        "X-Reduction-Percent": f"{reduction:.2f}",
    }
    if warnings:
        headers["X-Media-Warning"] = " | ".join(warnings)[:900].encode("ascii", "replace").decode("ascii")
    return headers
