from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
import ipaddress
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from backend.core.errors import PDFWorkbenchError


router = APIRouter(prefix="/desktop-native", tags=["desktop-native"])

_ARCHIVE_PATTERNS = (
    "*.zip *.7z *.rar *.tar *.tar.gz *.tgz *.tar.bz2 *.tbz2 "
    "*.tar.xz *.txz *.gz *.bz2 *.xz *.cab"
)
_ARCHIVE_SUFFIXES = (
    ".tar.gz", ".tar.bz2", ".tar.xz", ".tbz2", ".txz", ".zip",
    ".7z", ".rar", ".tgz", ".tar", ".gz", ".bz2", ".xz", ".cab",
)
_DIALOG_LOCK = threading.Lock()
_HASH_LOCK = threading.Lock()
_HASH_JOBS: dict[str, "_HashJob"] = {}
_HASH_EXECUTOR = ThreadPoolExecutor(
    max_workers=max(1, min(4, os.cpu_count() or 1)),
    thread_name_prefix="pdf-workbench-hash",
)
_FINISHED_JOB_TTL_SECONDS = 60 * 60


class _JsonModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PathPayload(_JsonModel):
    path: str = Field(min_length=1, max_length=32_767)


class ExtractArchivePayload(PathPayload):
    same_folder: bool = False
    password: str = Field(default="", max_length=4_096)


class SecureAllInOnePayload(PathPayload):
    password: str = Field(min_length=1, max_length=4_096)
    delete_original: bool = False
    reduce_size: bool = False


@dataclass
class _HashJob:
    job_id: str
    source: Path
    created_at: float = field(default_factory=time.monotonic)
    updated_at: float = field(default_factory=time.monotonic)
    status: Literal["running", "complete", "error"] = "running"
    progress: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None


def _require_local_request(request: Request) -> None:
    """Do not expose real filesystem paths to non-loopback clients."""
    host = request.client.host if request.client else ""
    if host == "testclient":
        return
    try:
        if ipaddress.ip_address(host).is_loopback:
            return
    except ValueError:
        pass
    raise HTTPException(status_code=403, detail="Desktop operations are available only from localhost.")


def _require_json(request: Request) -> None:
    media_type = request.headers.get("content-type", "").partition(";")[0].strip().lower()
    if media_type != "application/json":
        raise HTTPException(status_code=415, detail="Use an application/json request body.")


def _validated_path(raw_path: str, expected: Literal["file", "folder", "any"]) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip() or "\x00" in raw_path:
        raise HTTPException(status_code=400, detail="Choose a valid local path.")
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        raise HTTPException(status_code=400, detail="Local paths must be absolute.")
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail="The selected local path does not exist.") from exc
    if expected == "file" and not resolved.is_file():
        raise HTTPException(status_code=400, detail="Choose an existing local file.")
    if expected == "folder" and not resolved.is_dir():
        raise HTTPException(status_code=400, detail="Choose an existing local folder.")
    if expected == "any" and not (resolved.is_file() or resolved.is_dir()):
        raise HTTPException(status_code=400, detail="Choose an existing local file or folder.")
    return resolved


def _new_dialog_root():
    # Keep Tk out of module import/startup. Importing and creating it only after
    # a picker click avoids adding GUI work to the WebView startup path.
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
    except tk.TclError:
        pass
    root.update_idletasks()
    return root


def _windows_powershell() -> Path:
    windows_root = os.environ.get("SystemRoot") or os.environ.get("WINDIR")
    if windows_root:
        candidate = Path(windows_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        if candidate.is_file():
            return candidate
    discovered = shutil.which("powershell.exe")
    if discovered:
        return Path(discovered)
    raise RuntimeError("Windows PowerShell is required to open the file picker.")


def _run_windows_dialog(script: str, values: dict[str, str]) -> str | None:
    """Run a normal-user WinForms picker without depending on Tcl/Tk."""
    environment = os.environ.copy()
    environment.update(values)
    completed = subprocess.run(
        [
            str(_windows_powershell()),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-STA",
            "-Command",
            script,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode:
        detail = completed.stderr.strip() or "The Windows file picker could not open."
        raise RuntimeError(detail)
    selected = completed.stdout.strip()
    return selected or None


_WINDOWS_FILE_DIALOG = r"""
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.Application]::EnableVisualStyles()
$dialog = [System.Windows.Forms.OpenFileDialog]::new()
$dialog.Title = $env:LPW_DIALOG_TITLE
$dialog.Filter = $env:LPW_DIALOG_FILTER
$dialog.CheckFileExists = $true
$dialog.Multiselect = $false
$dialog.RestoreDirectory = $true
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    [Console]::Write($dialog.FileName)
}
"""


_WINDOWS_FOLDER_DIALOG = r"""
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.Application]::EnableVisualStyles()
$dialog = [System.Windows.Forms.FolderBrowserDialog]::new()
$dialog.Description = $env:LPW_DIALOG_TITLE
$dialog.ShowNewFolderButton = $true
if ($env:LPW_DIALOG_INITIAL) { $dialog.SelectedPath = $env:LPW_DIALOG_INITIAL }
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    [Console]::Write($dialog.SelectedPath)
}
"""


def _choose_file_dialog(*, archive_only: bool = False) -> str | None:
    if os.name == "nt":
        file_filter = (
            "Compressed files|*.zip;*.7z;*.rar;*.tar;*.tar.gz;*.tgz;*.tar.bz2;*.tbz2;"
            "*.tar.xz;*.txz;*.gz;*.bz2;*.xz;*.cab|All files|*.*"
            if archive_only
            else "All files|*.*"
        )
        return _run_windows_dialog(
            _WINDOWS_FILE_DIALOG,
            {
                "LPW_DIALOG_TITLE": (
                    "Choose a compressed file" if archive_only else "Choose a local file"
                ),
                "LPW_DIALOG_FILTER": file_filter,
            },
        )

    from tkinter import filedialog

    with _DIALOG_LOCK:
        root = _new_dialog_root()
        try:
            filetypes = (
                [("Compressed files", _ARCHIVE_PATTERNS), ("All files", "*.*")]
                if archive_only
                else [("All files", "*.*")]
            )
            selected = filedialog.askopenfilename(
                parent=root,
                title="Choose a compressed file" if archive_only else "Choose a local file",
                filetypes=filetypes,
            )
            return selected or None
        finally:
            root.destroy()


def _choose_folder_dialog(*, initial_folder: Path | None = None, title: str = "Choose a local folder") -> str | None:
    if os.name == "nt":
        return _run_windows_dialog(
            _WINDOWS_FOLDER_DIALOG,
            {
                "LPW_DIALOG_TITLE": title,
                "LPW_DIALOG_INITIAL": str(initial_folder) if initial_folder else "",
            },
        )

    from tkinter import filedialog

    with _DIALOG_LOCK:
        root = _new_dialog_root()
        try:
            selected = filedialog.askdirectory(
                parent=root,
                title=title,
                initialdir=str(initial_folder) if initial_folder else None,
                mustexist=True,
            )
            return selected or None
        finally:
            root.destroy()


def _file_payload(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "name": path.name,
        "bytes": path.stat().st_size,
        "kind": "file",
    }


def _folder_payload(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "name": path.name or str(path),
        "kind": "folder",
    }


async def _pick_file(request: Request, *, archive_only: bool = False):
    _require_local_request(request)
    _require_json(request)
    selected = await run_in_threadpool(_choose_file_dialog, archive_only=archive_only)
    if not selected:
        return None
    return _file_payload(_validated_path(selected, "file"))


async def _pick_folder(request: Request):
    _require_local_request(request)
    _require_json(request)
    selected = await run_in_threadpool(_choose_folder_dialog)
    if not selected:
        return None
    return _folder_payload(_validated_path(selected, "folder"))


@router.post("/choose/archive")
async def choose_archive(request: Request):
    return await _pick_file(request, archive_only=True)


@router.post("/choose/security-file")
async def choose_security_file(request: Request):
    return await _pick_file(request)


@router.post("/choose/security-folder")
async def choose_security_folder(request: Request):
    return await _pick_folder(request)


@router.post("/choose/hash-file")
async def choose_hash_file(request: Request):
    return await _pick_file(request)


@router.post("/choose/hash-folder")
async def choose_hash_folder(request: Request):
    return await _pick_folder(request)


def _archive_stem(path: Path) -> str:
    lower = path.name.lower()
    for suffix in _ARCHIVE_SUFFIXES:
        if lower.endswith(suffix):
            return path.name[:-len(suffix)] or "archive"
    return path.stem or "archive"


@router.post("/extract-archive")
async def extract_archive(payload: ExtractArchivePayload, request: Request):
    _require_local_request(request)
    _require_json(request)
    source = _validated_path(payload.path, "file")
    if payload.same_folder:
        output_root = source.parent
    else:
        selected = await run_in_threadpool(
            _choose_folder_dialog,
            initial_folder=source.parent,
            title="Choose extraction destination",
        )
        if not selected:
            return None
        output_root = _validated_path(selected, "folder")

    from backend.services.document_security.archive_extraction import extract_archive_any
    from backend.services.document_security.local_operations import unique_path

    destination = unique_path(output_root, f"{_archive_stem(source)}_extracted")
    try:
        result = await run_in_threadpool(
            extract_archive_any,
            source,
            destination,
            payload.password,
        )
    except (ValueError, PDFWorkbenchError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "path": str(result.destination),
        "files": result.file_count,
        "bytes": result.total_bytes,
        "type": result.archive_type,
    }


@router.post("/secure-all-in-one")
async def secure_all_in_one(payload: SecureAllInOnePayload, request: Request):
    _require_local_request(request)
    _require_json(request)
    source = _validated_path(payload.path, "any")

    from backend.services.document_security.local_operations import secure_local_file

    try:
        result = await run_in_threadpool(
            secure_local_file,
            source,
            payload.password,
            payload.delete_original,
            payload.reduce_size,
        )
    except (ValueError, PDFWorkbenchError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "path": str(result.output_path),
        "original_trashed": result.original_trashed,
        "note": result.note,
    }


def _progress_payload(
    *,
    started: float,
    completed: int,
    total: int,
    files_completed: int,
    files_total: int,
    current_name: str,
) -> dict[str, Any]:
    byte_ratio = completed / total if total else 0
    file_ratio = files_completed / files_total if files_total else 1
    percent = min(99, max(1, round((byte_ratio if total else file_ratio) * 100, 1)))
    return {
        "operation": "Calculating SHA-256",
        "stage": "Hashing local folder" if files_total != 1 else "Hashing local file",
        "percent": percent,
        "detail": (
            f"{files_completed:,}/{files_total:,} files • "
            f"{completed:,}/{total:,} bytes • {current_name}"
        ),
        "elapsed_seconds": time.monotonic() - started,
        "status": "running",
    }


def _cleanup_hash_jobs(now: float) -> None:
    expired = [
        job_id
        for job_id, job in _HASH_JOBS.items()
        if job.status != "running" and now - job.updated_at > _FINISHED_JOB_TTL_SECONDS
    ]
    for job_id in expired:
        _HASH_JOBS.pop(job_id, None)


def _run_hash_job(job_id: str, source: Path) -> None:
    from backend.services.document_security.hash_file import create_path_hash

    started = time.monotonic()

    def update(completed, total, files_completed, files_total, current_name):
        progress = _progress_payload(
            started=started,
            completed=completed,
            total=total,
            files_completed=files_completed,
            files_total=files_total,
            current_name=current_name,
        )
        with _HASH_LOCK:
            job = _HASH_JOBS.get(job_id)
            if job is not None:
                job.progress = progress
                job.updated_at = time.monotonic()

    try:
        result = create_path_hash(source, update)
        result_payload = {
            "name": result.name,
            "bytes": result.bytes,
            "sha256": result.sha256,
            "kind": result.kind,
            "files": result.files,
        }
        with _HASH_LOCK:
            job = _HASH_JOBS.get(job_id)
            if job is not None:
                job.status = "complete"
                job.result = result_payload
                job.progress = {
                    "operation": "Calculating SHA-256",
                    "stage": "SHA-256 ready",
                    "percent": 100,
                    "detail": result.name,
                    "elapsed_seconds": time.monotonic() - started,
                    "status": "complete",
                }
                job.updated_at = time.monotonic()
    except Exception as exc:
        with _HASH_LOCK:
            job = _HASH_JOBS.get(job_id)
            if job is not None:
                job.status = "error"
                job.error = str(exc) or exc.__class__.__name__
                job.progress = {
                    "operation": "Calculating SHA-256",
                    "stage": "Hashing failed",
                    "detail": job.error,
                    "elapsed_seconds": time.monotonic() - started,
                    "status": "error",
                }
                job.updated_at = time.monotonic()


def _job_payload(job: _HashJob) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "job_id": job.job_id,
        "status": job.status,
        "progress": dict(job.progress),
    }
    if job.result is not None:
        payload["result"] = dict(job.result)
    if job.error:
        payload["error"] = job.error
    return payload


@router.post("/hash/start", status_code=202)
async def start_hash(payload: PathPayload, request: Request):
    _require_local_request(request)
    _require_json(request)
    source = _validated_path(payload.path, "any")
    job_id = uuid4().hex
    now = time.monotonic()
    job = _HashJob(
        job_id=job_id,
        source=source,
        progress={
            "operation": "Calculating SHA-256",
            "stage": "Preparing local folder" if source.is_dir() else "Preparing local file",
            "percent": 1,
            "detail": source.name or str(source),
            "elapsed_seconds": 0,
            "status": "running",
        },
    )
    with _HASH_LOCK:
        _cleanup_hash_jobs(now)
        _HASH_JOBS[job_id] = job
    _HASH_EXECUTOR.submit(_run_hash_job, job_id, source)
    return _job_payload(job)


@router.get("/hash/jobs/{job_id}")
async def get_hash_job(job_id: str, request: Request):
    _require_local_request(request)
    if len(job_id) != 32 or any(character not in "0123456789abcdef" for character in job_id):
        raise HTTPException(status_code=404, detail="Hash job not found.")
    with _HASH_LOCK:
        _cleanup_hash_jobs(time.monotonic())
        job = _HASH_JOBS.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Hash job not found.")
        return _job_payload(job)
