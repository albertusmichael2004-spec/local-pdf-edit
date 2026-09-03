from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from backend.api.http_errors import bad_request, dependency_unavailable
from backend.api.workspace import RequestWorkspace
from backend.core.errors import MediaProcessingError, PDFWorkbenchError
from backend.services.media.facade import MediaJobFacade
from backend.services.media.models import JobOptions
from .helpers import output_headers, save_sources


router = APIRouter()


async def _run(files, operation: str, target: str, quality: str, keep_metadata: bool, kinds: set[str]) -> FileResponse:
    workspace = RequestWorkspace()
    try:
        sources = await save_sources(workspace, files)
        options = JobOptions(operation, target, quality, keep_metadata)
        result = await run_in_threadpool(MediaJobFacade().process, sources, workspace.output("media_outputs"), options, kinds)
        return workspace.download(result.path, result.media_type, result.download_name, output_headers(result.source_bytes, result.output_bytes, result.warnings))
    except MediaProcessingError as exc:
        workspace.cleanup_on_error()
        if any(word in str(exc).lower() for word in ("required", "install")):
            raise dependency_unavailable(exc) from exc
        raise bad_request(exc) from exc
    except (ValueError, PDFWorkbenchError) as exc:
        workspace.cleanup_on_error()
        raise bad_request(exc) from exc
    except Exception:
        workspace.cleanup_on_error()
        raise


@router.post("/compress/media")
async def compress_media(files: Annotated[list[UploadFile], File(...)], target_format: Annotated[str, Form()] = "keep", quality: Annotated[str, Form()] = "balanced", keep_metadata: Annotated[bool, Form()] = True):
    return await _run(files, "compressed", target_format, quality, keep_metadata, {"video", "audio"})


@router.post("/compress/images")
async def compress_images(files: Annotated[list[UploadFile], File(...)], target_format: Annotated[str, Form()] = "keep", quality: Annotated[str, Form()] = "balanced", keep_metadata: Annotated[bool, Form()] = True):
    return await _run(files, "compressed", target_format, quality, keep_metadata, {"image"})


@router.post("/convert/video")
async def convert_video(files: Annotated[list[UploadFile], File(...)], target_format: Annotated[str, Form()], quality: Annotated[str, Form()] = "balanced", keep_metadata: Annotated[bool, Form()] = True):
    return await _run(files, "converted", target_format, quality, keep_metadata, {"video"})


@router.post("/convert/audio")
async def convert_audio(files: Annotated[list[UploadFile], File(...)], target_format: Annotated[str, Form()], quality: Annotated[str, Form()] = "balanced", keep_metadata: Annotated[bool, Form()] = True):
    return await _run(files, "converted", target_format, quality, keep_metadata, {"audio"})


@router.post("/convert/images")
async def convert_images(files: Annotated[list[UploadFile], File(...)], target_format: Annotated[str, Form()], quality: Annotated[str, Form()] = "balanced", keep_metadata: Annotated[bool, Form()] = True):
    return await _run(files, "converted", target_format, quality, keep_metadata, {"image"})


@router.post("/convert/ebook")
async def convert_ebook(files: Annotated[list[UploadFile], File(...)], target_format: Annotated[str, Form()], quality: Annotated[str, Form()] = "balanced", keep_metadata: Annotated[bool, Form()] = True):
    return await _run(files, "converted", target_format, quality, keep_metadata, {"ebook", "pdf"})
