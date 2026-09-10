from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
from threading import RLock

from fastapi import UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from backend.utils.file_uploads import safe_filename, save_upload


_workspace_lock = RLock()
_active_workspaces: set[Path] = set()


class RequestWorkspace:
    """Owns one request's temporary files and cleanup lifecycle."""

    def __init__(self) -> None:
        self.path = Path(tempfile.mkdtemp(prefix="pdf-workbench-"))
        self._scheduled_cleanup = False
        with _workspace_lock:
            _active_workspaces.add(self.path)

    async def save_pdf(
        self,
        upload: UploadFile,
        fallback: str = "document.pdf",
        prefix: str = "",
    ) -> tuple[Path, str, int]:
        filename = safe_filename(upload.filename, fallback)
        path = self.path / f"{prefix}{filename}"
        size = await save_upload(upload, path, require_pdf=True)
        return path, filename, size

    async def save_file(
        self,
        upload: UploadFile,
        fallback: str,
        prefix: str = "",
    ) -> tuple[Path, str, int]:
        filename = safe_filename(upload.filename, fallback)
        path = self.path / f"{prefix}{filename}"
        size = await save_upload(upload, path, require_pdf=False)
        return path, filename, size

    async def save_media_file(
        self,
        upload: UploadFile,
        fallback: str,
        prefix: str = "",
    ) -> tuple[Path, str, int]:
        """Compatibility alias for media routes using the uncapped file spooler."""
        return await self.save_file(upload, fallback, prefix)

    def output(self, filename: str) -> Path:
        return self.path / filename

    def download(
        self,
        path: Path,
        media_type: str,
        filename: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> FileResponse:
        self._scheduled_cleanup = True
        return FileResponse(
            path,
            media_type=media_type,
            filename=filename or path.name,
            headers=headers,
            background=BackgroundTask(self.cleanup),
        )

    def cleanup(self) -> None:
        with _workspace_lock:
            _active_workspaces.discard(self.path)
        shutil.rmtree(self.path, ignore_errors=True)

    def cleanup_on_error(self) -> None:
        if not self._scheduled_cleanup:
            self.cleanup()


def cleanup_orphaned_workspaces() -> int:
    """Remove abandoned request folders without touching active requests."""
    temp_root = Path(tempfile.gettempdir())
    with _workspace_lock:
        active = set(_active_workspaces)

    removed = 0
    for path in temp_root.glob("pdf-workbench-*"):
        if not path.is_dir() or path in active:
            continue
        shutil.rmtree(path, ignore_errors=True)
        if not path.exists():
            removed += 1
    return removed
