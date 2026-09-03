from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    """Runtime settings for the localhost-only desktop application."""

    app_name: str = "Local PDF Workbench"
    host: str = os.getenv("PDF_TOOL_HOST", "127.0.0.1")
    port: int = int(os.getenv("PDF_TOOL_PORT", "8000"))
    ghostscript_timeout_seconds: int = int(
        os.getenv("PDF_TOOL_GS_TIMEOUT_SECONDS", "240")
    )
    media_timeout_seconds: int = int(os.getenv("PDF_TOOL_MEDIA_TIMEOUT_SECONDS", "3600"))
    media_workers: int = max(1, int(os.getenv("PDF_TOOL_MEDIA_WORKERS", "2")))

settings = Settings()
