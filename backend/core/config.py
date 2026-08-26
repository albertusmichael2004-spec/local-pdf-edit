from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    """Runtime settings for the localhost-only desktop application."""

    app_name: str = "Local PDF Workbench"
    host: str = os.getenv("PDF_TOOL_HOST", "127.0.0.1")
    port: int = int(os.getenv("PDF_TOOL_PORT", "8000"))
    max_file_mb: int = int(os.getenv("PDF_TOOL_MAX_FILE_MB", "250"))
    ghostscript_timeout_seconds: int = int(
        os.getenv("PDF_TOOL_GS_TIMEOUT_SECONDS", "240")
    )

    @property
    def max_file_bytes(self) -> int:
        return self.max_file_mb * 1024 * 1024


settings = Settings()
