from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from backend.api.http_errors import bad_request, dependency_unavailable
from backend.api.workspace import RequestWorkspace
from backend.core.errors import MediaProcessingError, PDFWorkbenchError
from backend.services.media.capabilities import capability_payload, targets_for
from backend.services.media.facade import MediaJobFacade
from .helpers import save_sources


router = APIRouter()


@router.get("/media/capabilities")
def capabilities() -> JSONResponse:
    return JSONResponse(capability_payload())


@router.post("/media/probe")
async def probe(files: Annotated[list[UploadFile], File(...)]) -> JSONResponse:
    workspace = RequestWorkspace()
    try:
        sources = await save_sources(workspace, files)
        results = await run_in_threadpool(MediaJobFacade().probe, sources)
        return JSONResponse({"files": [{
            "name": source.display_name, "kind": item.kind, "format": item.format,
            "mime_type": item.mime_type, "bytes": item.bytes, "details": item.details,
            "warnings": list(item.warnings), "targets": targets_for(item),
        } for source, item in results], "capabilities": capability_payload()})
    except MediaProcessingError as exc:
        if "required" in str(exc).lower():
            raise dependency_unavailable(exc) from exc
        raise bad_request(exc) from exc
    except (ValueError, PDFWorkbenchError) as exc:
        raise bad_request(exc) from exc
    finally:
        workspace.cleanup()
