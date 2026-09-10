from __future__ import annotations

from pathlib import Path

from fastapi import UploadFile

from backend.api.workspace import RequestWorkspace
from backend.services.workflow_session import workflow_store


async def resolve_pdf_input(
    workspace: RequestWorkspace,
    file: UploadFile | None,
    workflow_id: str | None,
    artifact_id: str | None,
    *,
    fallback: str = "document.pdf",
    prefix: str = "",
) -> tuple[Path, str, int]:
    """Resolve a normal upload or a server-side workflow artifact."""
    if workflow_id or artifact_id:
        if not workflow_id or not artifact_id:
            raise ValueError("Both workflow_id and artifact_id are required for a workflow transfer.")
        if file is not None:
            raise ValueError("Choose either an uploaded PDF or a workflow artifact, not both.")
        artifact = workflow_store.artifact(workflow_id, artifact_id)
        return artifact.path, artifact.file_name, artifact.bytes
    if file is None:
        raise ValueError("Choose or drop a PDF first.")
    return await workspace.save_pdf(file, fallback=fallback, prefix=prefix)
