from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from starlette.concurrency import run_in_threadpool

from backend.api.http_errors import bad_request, dependency_unavailable
from backend.core.config import settings
from backend.core.errors import CompressionError, OCRError, PDFWorkbenchError
from backend.services.edit_pdf.compress_pdf import compress_preset, compress_to_target_range
from backend.services.edit_pdf.ocr_pdf import ocr_pdf
from backend.services.edit_pdf.organize_pdf import organize_with_plan
from backend.services.edit_pdf.redact_pdf import redact_pdf, search_redaction_text, select_redaction_text
from backend.services.pdf_security.protect_pdf import protect_pdf
from backend.services.quick_tools.merge_pdf import merge_pdfs
from backend.services.shared.file_hash import sha256_file
from backend.services.workflow_session import WorkflowArtifact, workflow_store
from backend.utils.file_uploads import safe_filename, save_upload


router = APIRouter(prefix="/workflows")
TRANSFER_DESTINATIONS = {
    "split",
    "extract-pages",
    "watermark",
    "crop",
    "ocr",
    "redact",
    "compare-pdf",
}


def _artifact_payload(workflow_id: str, artifact: WorkflowArtifact) -> dict[str, object]:
    payload = artifact.public()
    base = f"/api/workflows/{workflow_id}/artifacts/{artifact.artifact_id}"
    payload.update({"content_url": f"{base}/content", "download_url": f"{base}/download"})
    return payload


def _parse_plan(plan_json: str) -> list[dict[str, object]]:
    try:
        plan = json.loads(plan_json)
    except json.JSONDecodeError as exc:
        raise ValueError("The page editor plan is not valid JSON.") from exc
    if not isinstance(plan, list) or not plan:
        raise ValueError("The organized PDF must contain at least one page.")
    if not all(isinstance(entry, dict) for entry in plan):
        raise ValueError("Every page editor plan item must be an object.")
    return plan


def _stable_output_page_ids(
    source: WorkflowArtifact,
    plan: list[dict[str, object]],
) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for position, entry in enumerate(plan, start=1):
        source_page = entry.get("source_page")
        if source_page is None:
            page_id = str(entry.get("page_id") or f"blank_{uuid4().hex}")
        else:
            try:
                page_number = int(source_page)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Page {position}: source_page must be a page number or null.") from exc
            if page_number < 1 or page_number > source.page_count:
                raise ValueError(
                    f"Page {position}: source page {page_number} is outside 1-{source.page_count}."
                )
            expected_source_id = source.page_ids[page_number - 1]
            supplied_source_id = entry.get("source_page_id")
            if supplied_source_id and str(supplied_source_id) != expected_source_id:
                raise ValueError(
                    f"Page {position}: the saved page identity no longer matches source page {page_number}."
                )
            page_id = str(entry.get("page_id") or expected_source_id)

        if not page_id or page_id in seen:
            page_id = f"instance_{uuid4().hex}"
        seen.add(page_id)
        output.append(page_id)
    return output


def _stable_output_page_sources(
    source: WorkflowArtifact,
    plan: list[dict[str, object]],
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for entry in plan:
        source_page = entry.get("source_page")
        if source_page is None:
            output.append({
                "source_artifact_id": None,
                "file_name": "Blank page",
                "source_page": None,
            })
            continue
        output.append(dict(source.page_sources[int(source_page) - 1]))
    return output


async def _save_source_uploads(
    workflow_id: str,
    uploads: list[UploadFile],
    *,
    make_first_original: bool = False,
) -> list[WorkflowArtifact]:
    artifacts: list[WorkflowArtifact] = []
    for index, upload in enumerate(uploads, start=1):
        filename = safe_filename(upload.filename, f"document_{index}.pdf")
        path = workflow_store.reserve_path(workflow_id, filename)
        await save_upload(upload, path, require_pdf=True)
        artifacts.append(await run_in_threadpool(
            workflow_store.register_pdf,
            workflow_id,
            path,
            filename,
            "upload" if make_first_original and index == 1 else "merge-source",
            make_original=make_first_original and index == 1,
        ))
    return artifacts


async def _combined_organize_source(
    workflow_id: str,
    sources: list[WorkflowArtifact],
) -> WorkflowArtifact:
    if not sources:
        raise ValueError("Add at least one PDF to the workflow.")
    if len(sources) == 1:
        workflow_store.set_current(workflow_id, sources[0].artifact_id)
        return sources[0]

    output_name = f"{Path(sources[0].file_name).stem}_merged.pdf"
    output_path = workflow_store.reserve_path(workflow_id, output_name)
    total_pages = await run_in_threadpool(
        merge_pdfs,
        [artifact.path for artifact in sources],
        output_path,
    )
    page_ids = [page_id for artifact in sources for page_id in artifact.page_ids]
    page_sources = [source for artifact in sources for source in artifact.page_sources]
    merged = await run_in_threadpool(
        workflow_store.register_pdf,
        workflow_id,
        output_path,
        output_name,
        "merge",
        parent_artifact_id=sources[0].artifact_id,
        page_ids=page_ids,
        page_sources=page_sources,
    )
    if total_pages != merged.page_count:
        raise ValueError("The merged page count could not be verified.")
    return merged


@router.post("/organize/start")
async def start_organize_workflow(
    files: Annotated[list[UploadFile] | None, File()] = None,
    file: Annotated[UploadFile | None, File()] = None,
) -> JSONResponse:
    session = workflow_store.create()
    try:
        uploads = list(files or [])
        if file is not None:
            uploads.insert(0, file)
        if not uploads:
            raise ValueError("Add at least one PDF to the workflow.")
        sources = await _save_source_uploads(
            session.workflow_id,
            uploads,
            make_first_original=True,
        )
        artifact = await _combined_organize_source(session.workflow_id, sources)
        return JSONResponse({
            "workflow": workflow_store.summary(session.workflow_id),
            "artifact": _artifact_payload(session.workflow_id, artifact),
            "source_artifacts": [
                _artifact_payload(session.workflow_id, source) for source in sources
            ],
            "execution_order": ["merge"] if len(sources) > 1 else [],
        })
    except (ValueError, PDFWorkbenchError) as exc:
        workflow_store.delete(session.workflow_id)
        raise bad_request(exc) from exc
    except Exception:
        workflow_store.delete(session.workflow_id)
        raise


@router.post("/redact/start")
async def start_redact_workflow(
    files: Annotated[list[UploadFile] | None, File()] = None,
    file: Annotated[UploadFile | None, File()] = None,
) -> JSONResponse:
    """Start Redact PDF with one or more source PDFs in merge order."""
    return await start_organize_workflow(files=files, file=file)


@router.post("/{workflow_id}/organize/merge")
async def merge_organize_sources(
    workflow_id: str,
    files: Annotated[list[UploadFile], File(...)],
    base_artifact_id: Annotated[str, Form()],
) -> JSONResponse:
    try:
        if not files:
            raise ValueError("Add at least one PDF to merge with the current source.")
        base = workflow_store.artifact(workflow_id, base_artifact_id)
        inputs = [base]
        for index, upload in enumerate(files, start=1):
            filename = safe_filename(upload.filename, f"document_{index}.pdf")
            path = workflow_store.reserve_path(workflow_id, filename)
            await save_upload(upload, path, require_pdf=True)
            inputs.append(await run_in_threadpool(
                workflow_store.register_pdf,
                workflow_id,
                path,
                filename,
                "merge-source",
            ))

        output_name = f"{Path(base.file_name).stem}_merged.pdf"
        output_path = workflow_store.reserve_path(workflow_id, output_name)
        total_pages = await run_in_threadpool(
            merge_pdfs,
            [artifact.path for artifact in inputs],
            output_path,
        )
        page_ids = [page_id for artifact in inputs for page_id in artifact.page_ids]
        merged = await run_in_threadpool(
            workflow_store.register_pdf,
            workflow_id,
            output_path,
            output_name,
            "merge",
            parent_artifact_id=base.artifact_id,
            page_ids=page_ids,
            page_sources=[source for artifact in inputs for source in artifact.page_sources],
        )
        if total_pages != merged.page_count:
            raise ValueError("The merged page count could not be verified.")
        return JSONResponse({
            "workflow": workflow_store.summary(workflow_id),
            "artifact": _artifact_payload(workflow_id, merged),
            "execution_order": ["merge"],
        })
    except (ValueError, PDFWorkbenchError) as exc:
        raise bad_request(exc) from exc


@router.post("/{workflow_id}/organize/sources")
async def reconcile_organize_sources(
    workflow_id: str,
    kept_artifact_ids_json: Annotated[str, Form()] = "[]",
    files: Annotated[list[UploadFile] | None, File()] = None,
) -> JSONResponse:
    try:
        try:
            kept_ids = json.loads(kept_artifact_ids_json)
        except json.JSONDecodeError as exc:
            raise ValueError("The retained source list is not valid JSON.") from exc
        if not isinstance(kept_ids, list) or not all(isinstance(item, str) for item in kept_ids):
            raise ValueError("The retained source list must contain artifact IDs.")
        if len(set(kept_ids)) != len(kept_ids):
            raise ValueError("The retained source list contains duplicates.")

        sources: list[WorkflowArtifact] = []
        for artifact_id in kept_ids:
            artifact = workflow_store.artifact(workflow_id, artifact_id)
            if artifact.source_operation not in {"upload", "merge-source"}:
                raise ValueError("Only original uploaded PDFs can be retained as workflow sources.")
            sources.append(artifact)
        sources.extend(await _save_source_uploads(workflow_id, list(files or [])))
        combined = await _combined_organize_source(workflow_id, sources)
        return JSONResponse({
            "workflow": workflow_store.summary(workflow_id),
            "artifact": _artifact_payload(workflow_id, combined),
            "source_artifacts": [
                _artifact_payload(workflow_id, source) for source in sources
            ],
            "execution_order": ["merge"] if len(sources) > 1 else [],
        })
    except (ValueError, PDFWorkbenchError) as exc:
        raise bad_request(exc) from exc


@router.post("/{workflow_id}/redact/sources")
async def reconcile_redact_sources(
    workflow_id: str,
    kept_artifact_ids_json: Annotated[str, Form()] = "[]",
    files: Annotated[list[UploadFile] | None, File()] = None,
) -> JSONResponse:
    """Rebuild the Redact source list, including a transferred workflow artifact."""
    try:
        try:
            kept_ids = json.loads(kept_artifact_ids_json)
        except json.JSONDecodeError as exc:
            raise ValueError("The retained source list is not valid JSON.") from exc
        if not isinstance(kept_ids, list) or not all(isinstance(item, str) for item in kept_ids):
            raise ValueError("The retained source list must contain artifact IDs.")
        if len(set(kept_ids)) != len(kept_ids):
            raise ValueError("The retained source list contains duplicates.")

        sources: list[WorkflowArtifact] = []
        for artifact_id in kept_ids:
            artifact = workflow_store.artifact(workflow_id, artifact_id)
            if artifact.source_operation == "protect":
                raise ValueError("A protected PDF must be unlocked before it can be redacted.")
            sources.append(artifact)
        sources.extend(await _save_source_uploads(workflow_id, list(files or [])))
        combined = await _combined_organize_source(workflow_id, sources)
        return JSONResponse({
            "workflow": workflow_store.summary(workflow_id),
            "artifact": _artifact_payload(workflow_id, combined),
            "source_artifacts": [
                _artifact_payload(workflow_id, source) for source in sources
            ],
            "execution_order": ["merge"] if len(sources) > 1 else [],
        })
    except (ValueError, PDFWorkbenchError) as exc:
        raise bad_request(exc) from exc


@router.post("/{workflow_id}/redact/prepare")
async def prepare_redact_pages(
    workflow_id: str,
    artifact_id: Annotated[str, Form()],
    plan_json: Annotated[str, Form()],
) -> JSONResponse:
    """Materialize optional page changes before the user draws final marks."""
    try:
        source = workflow_store.artifact(workflow_id, artifact_id)
        plan = _parse_plan(plan_json)
        page_ids = _stable_output_page_ids(source, plan)
        page_sources = _stable_output_page_sources(source, plan)
        output_name = f"{Path(source.file_name).stem}_prepared.pdf"
        output_path = workflow_store.reserve_path(workflow_id, output_name)
        await run_in_threadpool(organize_with_plan, source.path, output_path, plan)
        prepared = await run_in_threadpool(
            workflow_store.register_pdf,
            workflow_id,
            output_path,
            output_name,
            "prepare-pages",
            parent_artifact_id=source.artifact_id,
            page_ids=page_ids,
            page_sources=page_sources,
        )
        return JSONResponse({
            "workflow": workflow_store.summary(workflow_id),
            "artifact": _artifact_payload(workflow_id, prepared),
            "execution_order": ["prepare-pages"],
        })
    except (ValueError, PDFWorkbenchError) as exc:
        raise bad_request(exc) from exc


@router.post("/{workflow_id}/redact/search")
async def search_redact_workflow(
    workflow_id: str,
    artifact_id: Annotated[str, Form()],
    query: Annotated[str, Form()],
    exact: Annotated[bool, Form()] = False,
) -> JSONResponse:
    try:
        artifact = workflow_store.artifact(workflow_id, artifact_id)
        matches = await run_in_threadpool(
            search_redaction_text,
            artifact.path,
            query,
            artifact.page_ids,
            exact=exact,
        )
        return JSONResponse({
            "artifact_id": artifact.artifact_id,
            "query": query,
            "exact": exact,
            "matches": matches,
            "match_count": len(matches),
        })
    except (ValueError, PDFWorkbenchError) as exc:
        raise bad_request(exc) from exc


@router.post("/{workflow_id}/redact/select-text")
async def select_redact_workflow_text(
    workflow_id: str,
    artifact_id: Annotated[str, Form()],
    page_number: Annotated[int, Form()],
    page_instance_id: Annotated[str, Form()],
    rect_json: Annotated[str, Form()],
) -> JSONResponse:
    try:
        artifact = workflow_store.artifact(workflow_id, artifact_id)
        selection = json.loads(rect_json)
        if not isinstance(selection, dict):
            raise ValueError("The dragged text selection is not valid.")
        matches = await run_in_threadpool(
            select_redaction_text,
            artifact.path,
            artifact.page_ids,
            page_number,
            page_instance_id,
            selection,
        )
        return JSONResponse({
            "artifact_id": artifact.artifact_id,
            "matches": matches,
            "match_count": len(matches),
        })
    except (json.JSONDecodeError, ValueError, PDFWorkbenchError) as exc:
        raise bad_request(exc) from exc


@router.post("/{workflow_id}/organize/execute")
async def execute_organize_workflow(
    workflow_id: str,
    artifact_id: Annotated[str, Form()],
    plan_json: Annotated[str, Form()],
    compress_mode: Annotated[str | None, Form()] = None,
    target_min_mb: Annotated[float | None, Form()] = None,
    target_max_mb: Annotated[float | None, Form()] = None,
    protect_password: Annotated[str | None, Form()] = None,
    generate_sha256: Annotated[bool, Form()] = False,
) -> JSONResponse:
    try:
        source = workflow_store.artifact(workflow_id, artifact_id)
        plan = _parse_plan(plan_json)
        page_ids = _stable_output_page_ids(source, plan)
        page_sources = _stable_output_page_sources(source, plan)
        operations: list[dict[str, object]] = []
        execution_order: list[str] = []
        if source.source_operation == "merge":
            execution_order.append("merge")
        operations.append({"operation": "organize", "plan": plan})
        execution_order.append("organize")
        if compress_mode:
            if compress_mode == "custom":
                if target_min_mb is None or target_max_mb is None:
                    raise ValueError("Custom compression requires minimum and maximum target sizes.")
                if target_min_mb <= 0 or target_max_mb <= 0 or target_min_mb > target_max_mb:
                    raise ValueError("Enter a valid custom size range where min <= max and both are > 0.")
            operations.append({
                "operation": "compress",
                "mode": compress_mode,
                "target_min_mb": target_min_mb,
                "target_max_mb": target_max_mb,
            })
            execution_order.append("compress")
        if protect_password:
            operations.append({"operation": "protect"})
            execution_order.append("protect")
        if generate_sha256:
            operations.append({"operation": "sha256"})
            execution_order.append("sha256")
        workflow_store.set_operation_plan(workflow_id, operations)

        organized_name = f"{Path(source.file_name).stem}_organized.pdf"
        organized_path = workflow_store.reserve_path(workflow_id, organized_name)
        await run_in_threadpool(organize_with_plan, source.path, organized_path, plan)
        current = await run_in_threadpool(
            workflow_store.register_pdf,
            workflow_id,
            organized_path,
            organized_name,
            "organize",
            parent_artifact_id=source.artifact_id,
            page_ids=page_ids,
            page_sources=page_sources,
        )

        compression: dict[str, object] | None = None
        if compress_mode:
            compressed_name = f"{Path(current.file_name).stem}_compressed.pdf"
            compressed_path = workflow_store.reserve_path(workflow_id, compressed_name)
            if compress_mode == "custom":
                result = await run_in_threadpool(
                    compress_to_target_range,
                    current.path,
                    compressed_path,
                    int(target_min_mb * 1024 * 1024),
                    int(target_max_mb * 1024 * 1024),
                    settings.ghostscript_timeout_seconds,
                )
            else:
                result = await run_in_threadpool(
                    compress_preset,
                    current.path,
                    compressed_path,
                    compress_mode,
                    settings.ghostscript_timeout_seconds,
                )
            current = await run_in_threadpool(
                workflow_store.register_pdf,
                workflow_id,
                compressed_path,
                compressed_name,
                "compress",
                parent_artifact_id=current.artifact_id,
                page_ids=current.page_ids,
                page_sources=current.page_sources,
            )
            compression = {
                "mode": result.mode,
                "original_bytes": result.original_bytes,
                "output_bytes": result.output_bytes,
                "reduction_percent": result.reduction_percent,
                "note": result.note,
            }

        if protect_password:
            protected_name = f"{Path(current.file_name).stem}_protected.pdf"
            protected_path = workflow_store.reserve_path(workflow_id, protected_name)
            await run_in_threadpool(protect_pdf, current.path, protected_path, protect_password)
            current = await run_in_threadpool(
                workflow_store.register_pdf,
                workflow_id,
                protected_path,
                protected_name,
                "protect",
                parent_artifact_id=current.artifact_id,
                page_ids=current.page_ids,
                page_sources=current.page_sources,
                page_count=current.page_count,
            )

        digest = await run_in_threadpool(sha256_file, current.path) if generate_sha256 else None
        return JSONResponse({
            "workflow": workflow_store.summary(workflow_id),
            "artifact": _artifact_payload(workflow_id, current),
            "execution_order": execution_order,
            "sha256": digest,
            "compression": compression,
            "transfer_destinations": [] if protect_password else sorted(TRANSFER_DESTINATIONS),
        })
    except CompressionError as exc:
        if "Ghostscript" in str(exc) and "not found" in str(exc):
            raise dependency_unavailable(exc) from exc
        raise bad_request(exc) from exc
    except (ValueError, PDFWorkbenchError) as exc:
        raise bad_request(exc) from exc


@router.post("/{workflow_id}/redact/execute")
async def execute_redact_workflow(
    workflow_id: str,
    artifact_id: Annotated[str, Form()],
    redactions_json: Annotated[str, Form()],
    appearance: Annotated[str, Form()] = "black",
    color: Annotated[str, Form()] = "#000000",
    ocr_enabled: Annotated[bool, Form()] = False,
    ocr_language: Annotated[str, Form()] = "eng",
    ocr_dpi: Annotated[int, Form()] = 200,
    compress_mode: Annotated[str | None, Form()] = None,
    target_min_mb: Annotated[float | None, Form()] = None,
    target_max_mb: Annotated[float | None, Form()] = None,
    protect_password: Annotated[str | None, Form()] = None,
    generate_sha256: Annotated[bool, Form()] = False,
) -> JSONResponse:
    """Run secure redaction and preserve its artifact if an optional step fails."""
    try:
        try:
            redactions = json.loads(redactions_json)
        except json.JSONDecodeError as exc:
            raise ValueError("The redaction mark list is not valid JSON.") from exc
        if not isinstance(redactions, list):
            raise ValueError("The redaction mark list must be a list.")
        if compress_mode == "custom":
            if target_min_mb is None or target_max_mb is None:
                raise ValueError("Custom compression requires minimum and maximum target sizes.")
            if target_min_mb <= 0 or target_max_mb <= 0 or target_min_mb > target_max_mb:
                raise ValueError("Enter a valid custom size range where min <= max and both are > 0.")

        current = workflow_store.artifact(workflow_id, artifact_id)
        operations: list[dict[str, object]] = []
        completed_steps: list[str] = []
        failures: list[dict[str, str]] = []
        if current.source_operation == "merge":
            completed_steps.append("merge")
        elif current.source_operation == "prepare-pages":
            completed_steps.append("prepare-pages")

        if ocr_enabled:
            operations.append({"operation": "ocr", "language": ocr_language, "dpi": ocr_dpi})
            ocr_name = f"{Path(current.file_name).stem}_ocr.pdf"
            ocr_path = workflow_store.reserve_path(workflow_id, ocr_name)
            try:
                await run_in_threadpool(
                    ocr_pdf,
                    current.path,
                    ocr_path,
                    ocr_language,
                    min(300, max(120, ocr_dpi)),
                )
                current = await run_in_threadpool(
                    workflow_store.register_pdf,
                    workflow_id,
                    ocr_path,
                    ocr_name,
                    "ocr",
                    parent_artifact_id=current.artifact_id,
                    page_ids=current.page_ids,
                    page_sources=current.page_sources,
                )
                completed_steps.append("ocr")
            except (OCRError, PDFWorkbenchError, ValueError) as exc:
                ocr_path.unlink(missing_ok=True)
                failures.append({"step": "ocr", "message": str(exc)})

        comparison_artifact = current
        operations.append({
            "operation": "redact",
            "appearance": appearance,
            "mark_count": len(redactions),
        })
        redacted_name = f"{Path(current.file_name).stem}_redacted.pdf"
        redacted_path = workflow_store.reserve_path(workflow_id, redacted_name)
        redaction = await run_in_threadpool(
            redact_pdf,
            current.path,
            redacted_path,
            redactions,
            current.page_ids,
            appearance,
            color,
        )
        current = await run_in_threadpool(
            workflow_store.register_pdf,
            workflow_id,
            redacted_path,
            redacted_name,
            "redact",
            parent_artifact_id=current.artifact_id,
            page_ids=current.page_ids,
            page_sources=current.page_sources,
        )
        sanitized_artifact = current
        completed_steps.append("redact")

        compression: dict[str, object] | None = None
        if compress_mode:
            operations.append({
                "operation": "compress",
                "mode": compress_mode,
                "target_min_mb": target_min_mb,
                "target_max_mb": target_max_mb,
            })
            compressed_name = f"{Path(current.file_name).stem}_compressed.pdf"
            compressed_path = workflow_store.reserve_path(workflow_id, compressed_name)
            try:
                if compress_mode == "custom":
                    compression_result = await run_in_threadpool(
                        compress_to_target_range,
                        current.path,
                        compressed_path,
                        int(target_min_mb * 1024 * 1024),
                        int(target_max_mb * 1024 * 1024),
                        settings.ghostscript_timeout_seconds,
                    )
                else:
                    compression_result = await run_in_threadpool(
                        compress_preset,
                        current.path,
                        compressed_path,
                        compress_mode,
                        settings.ghostscript_timeout_seconds,
                    )
                current = await run_in_threadpool(
                    workflow_store.register_pdf,
                    workflow_id,
                    compressed_path,
                    compressed_name,
                    "compress",
                    parent_artifact_id=current.artifact_id,
                    page_ids=current.page_ids,
                    page_sources=current.page_sources,
                )
                compression = {
                    "mode": compression_result.mode,
                    "original_bytes": compression_result.original_bytes,
                    "output_bytes": compression_result.output_bytes,
                    "reduction_percent": compression_result.reduction_percent,
                    "note": compression_result.note,
                }
                completed_steps.append("compress")
            except (CompressionError, PDFWorkbenchError, ValueError) as exc:
                compressed_path.unlink(missing_ok=True)
                failures.append({"step": "compress", "message": str(exc)})

        protected = False
        if protect_password:
            operations.append({"operation": "protect"})
            protected_name = f"{Path(current.file_name).stem}_protected.pdf"
            protected_path = workflow_store.reserve_path(workflow_id, protected_name)
            try:
                await run_in_threadpool(protect_pdf, current.path, protected_path, protect_password)
                current = await run_in_threadpool(
                    workflow_store.register_pdf,
                    workflow_id,
                    protected_path,
                    protected_name,
                    "protect",
                    parent_artifact_id=current.artifact_id,
                    page_ids=current.page_ids,
                    page_sources=current.page_sources,
                    page_count=current.page_count,
                )
                protected = True
                completed_steps.append("protect")
            except (PDFWorkbenchError, ValueError) as exc:
                protected_path.unlink(missing_ok=True)
                failures.append({"step": "protect", "message": str(exc)})

        digest: str | None = None
        if generate_sha256:
            operations.append({"operation": "sha256"})
            try:
                digest = await run_in_threadpool(sha256_file, current.path)
                completed_steps.append("sha256")
            except (OSError, ValueError) as exc:
                failures.append({"step": "sha256", "message": str(exc)})

        workflow_store.set_operation_plan(workflow_id, operations)
        return JSONResponse({
            "workflow": workflow_store.summary(workflow_id),
            "artifact": _artifact_payload(workflow_id, current),
            "redacted_artifact": _artifact_payload(workflow_id, sanitized_artifact),
            "comparison_artifact": _artifact_payload(workflow_id, comparison_artifact),
            "execution_order": completed_steps,
            "redaction": redaction.public(),
            "sha256": digest,
            "compression": compression,
            "failures": failures,
            "transfer_destinations": [] if protected else sorted(TRANSFER_DESTINATIONS - {"redact"}),
        })
    except (ValueError, PDFWorkbenchError) as exc:
        raise bad_request(exc) from exc


@router.post("/{workflow_id}/transfer")
def prepare_transfer(
    workflow_id: str,
    artifact_id: Annotated[str, Form()],
    destination: Annotated[str, Form()],
    source_feature: Annotated[str, Form()] = "organize",
    comparison_artifact_id: Annotated[str | None, Form()] = None,
) -> JSONResponse:
    try:
        if destination not in TRANSFER_DESTINATIONS:
            raise ValueError("This workflow destination is not available.")
        artifact = workflow_store.artifact(workflow_id, artifact_id)
        if artifact.source_operation == "protect":
            raise ValueError("A protected PDF must be unlocked before it can continue to editing tools.")
        comparison_artifact = None
        if destination == "compare-pdf":
            if not comparison_artifact_id:
                raise ValueError("Compare PDF requires the original workflow artifact.")
            comparison_artifact = workflow_store.artifact(workflow_id, comparison_artifact_id)
        workflow_store.push_return(workflow_id, source_feature, artifact_id)
        return JSONResponse({
            "workflow": workflow_store.summary(workflow_id),
            "artifact": _artifact_payload(workflow_id, artifact),
            "comparison_artifact": (
                _artifact_payload(workflow_id, comparison_artifact)
                if comparison_artifact is not None
                else None
            ),
            "destination": destination,
        })
    except (ValueError, PDFWorkbenchError) as exc:
        raise bad_request(exc) from exc


@router.get("/{workflow_id}")
def get_workflow(workflow_id: str) -> JSONResponse:
    try:
        return JSONResponse(workflow_store.summary(workflow_id))
    except PDFWorkbenchError as exc:
        raise bad_request(exc) from exc


@router.get("/{workflow_id}/artifacts/{artifact_id}/content")
def artifact_content(workflow_id: str, artifact_id: str) -> FileResponse:
    try:
        artifact = workflow_store.artifact(workflow_id, artifact_id)
        return FileResponse(artifact.path, media_type=artifact.media_type)
    except PDFWorkbenchError as exc:
        raise bad_request(exc) from exc


@router.get("/{workflow_id}/artifacts/{artifact_id}")
def artifact_metadata(workflow_id: str, artifact_id: str) -> JSONResponse:
    try:
        artifact = workflow_store.artifact(workflow_id, artifact_id)
        return JSONResponse(_artifact_payload(workflow_id, artifact))
    except PDFWorkbenchError as exc:
        raise bad_request(exc) from exc


@router.get("/{workflow_id}/artifacts/{artifact_id}/download")
def download_artifact(workflow_id: str, artifact_id: str) -> FileResponse:
    try:
        artifact = workflow_store.artifact(workflow_id, artifact_id)
        return FileResponse(
            artifact.path,
            media_type=artifact.media_type,
            filename=artifact.file_name,
        )
    except PDFWorkbenchError as exc:
        raise bad_request(exc) from exc


@router.delete("/{workflow_id}")
def finish_workflow(workflow_id: str) -> JSONResponse:
    removed = workflow_store.delete(workflow_id)
    return JSONResponse({"status": "finished", "removed": removed})
