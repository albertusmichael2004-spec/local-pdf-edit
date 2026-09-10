from __future__ import annotations

from io import BytesIO
import base64
import json
from pathlib import Path

import fitz
from fastapi.testclient import TestClient
from PIL import Image

from backend.core.errors import CompressionError
from backend.main import app
from backend.services.edit_pdf.redact_pdf import redact_pdf, search_redaction_text, select_redaction_text
from backend.services.shared.preview import render_page_preview
from backend.services.workflow_session import workflow_store


def _upload(path: Path) -> tuple[str, bytes, str]:
    return path.name, path.read_bytes(), "application/pdf"


def _sensitive_pdf(path: Path, *, rotation: int = 0, label: str = "SECRET SALARY 24500000") -> Path:
    with fitz.open() as document:
        page = document.new_page(width=400, height=600)
        page.insert_text((50, 75), "Public heading", fontsize=16)
        page.insert_text((50, 135), label, fontsize=18)
        if rotation:
            page.set_rotation(rotation)
        document.save(path)
    return path


def test_secure_redaction_removes_searchable_text_on_rotated_page(tmp_path: Path):
    source = _sensitive_pdf(tmp_path / "rotated.pdf", rotation=90)
    output = tmp_path / "redacted.pdf"
    page_ids = ["stable-page-1"]
    matches = search_redaction_text(source, "SECRET SALARY 24500000", page_ids)

    assert len(matches) == 1
    assert matches[0]["page_instance_id"] == "stable-page-1"
    result = redact_pdf(source, output, matches, page_ids, "black", "#000000")

    assert result.verified is True
    assert result.marks_applied == 1
    with fitz.open(output) as document:
        text = document[0].get_text()
        assert "SECRET" not in text
        assert "24500000" not in text
        assert "Public heading" in text


def test_secure_blur_is_reinserted_only_after_underlying_content_is_removed(tmp_path: Path):
    source = _sensitive_pdf(tmp_path / "blur-source.pdf")
    output = tmp_path / "blur-redacted.pdf"
    page_ids = ["stable-page-1"]
    marks = search_redaction_text(source, "SECRET SALARY 24500000", page_ids)

    result = redact_pdf(source, output, marks, page_ids, "blur", "#000000")

    assert result.verified is True
    with fitz.open(output) as document:
        assert "SECRET SALARY" not in document[0].get_text()
        assert len(document[0].get_images(full=True)) >= 1


def test_exact_text_search_rejects_substrings_but_keeps_punctuation(tmp_path: Path):
    source = _sensitive_pdf(tmp_path / "exact.pdf", label="ID dividend identifier ID:")
    page_ids = ["stable-page-1"]

    broad = search_redaction_text(source, "ID", page_ids)
    exact = search_redaction_text(source, "ID", page_ids, exact=True)

    assert len(broad) > len(exact)
    assert len(exact) == 2


def test_redact_editor_can_request_a_high_definition_page_preview(tmp_path: Path):
    source = _sensitive_pdf(tmp_path / "hd-preview.pdf")

    preview = render_page_preview(source, 1, max_width=2400)
    payload = preview.image.split(",", 1)[1]
    with Image.open(BytesIO(base64.b64decode(payload))) as image:
        assert image.format == "PNG"
        assert image.width == 2400


def test_dragged_text_selection_resolves_real_pdf_character_bounds(tmp_path: Path):
    source = _sensitive_pdf(tmp_path / "drag-text.pdf", label="ALPHA BETA GAMMA")
    with fitz.open(source) as document:
        page = document[0]
        match = page.search_for("BETA")[0] * page.rotation_matrix
        visible = page.rect
        selection = {
            "space": "normalized_view",
            "x0": match.x0 / visible.width,
            "y0": match.y0 / visible.height,
            "x1": match.x1 / visible.width,
            "y1": match.y1 / visible.height,
        }

    marks = select_redaction_text(source, ["stable-page-1"], 1, "stable-page-1", selection)

    assert len(marks) == 1
    assert marks[0]["source"] == "text_selection"
    assert marks[0]["search_text"] == "BETA"


def test_redact_integrated_workflow_merges_searches_executes_and_compares(tmp_path: Path):
    first = _sensitive_pdf(tmp_path / "employee.pdf")
    second = _sensitive_pdf(tmp_path / "appendix.pdf", label="APPENDIX PRIVATE")
    workflow_id = None
    with TestClient(app) as client:
        started = client.post(
            "/api/workflows/redact/start",
            files=[("files", _upload(first)), ("files", _upload(second))],
        )
        assert started.status_code == 200, started.text
        payload = started.json()
        workflow_id = payload["workflow"]["workflow_id"]
        merged = payload["artifact"]
        assert merged["page_count"] == 2
        assert payload["execution_order"] == ["merge"]

        searched = client.post(
            f"/api/workflows/{workflow_id}/redact/search",
            data={"artifact_id": merged["artifact_id"], "query": "SECRET SALARY 24500000"},
        )
        assert searched.status_code == 200, searched.text
        marks = searched.json()["matches"]
        assert len(marks) == 1

        appendix_match = client.post(
            f"/api/workflows/{workflow_id}/redact/search",
            data={"artifact_id": merged["artifact_id"], "query": "APPENDIX PRIVATE"},
        ).json()["matches"][0]
        dragged = client.post(
            f"/api/workflows/{workflow_id}/redact/select-text",
            data={
                "artifact_id": merged["artifact_id"],
                "page_number": appendix_match["page_number"],
                "page_instance_id": appendix_match["page_instance_id"],
                "rect_json": json.dumps(appendix_match["rect"]),
            },
        )
        assert dragged.status_code == 200, dragged.text
        dragged_marks = dragged.json()["matches"]
        assert dragged_marks[0]["source"] == "text_selection"
        marks.extend(dragged_marks)

        executed = client.post(
            f"/api/workflows/{workflow_id}/redact/execute",
            data={
                "artifact_id": merged["artifact_id"],
                "redactions_json": json.dumps(marks),
                "appearance": "black",
                "generate_sha256": "true",
            },
        )
        assert executed.status_code == 200, executed.text
        result = executed.json()
        artifact = result["artifact"]
        original = result["comparison_artifact"]
        assert result["redaction"]["verified"] is True
        assert result["execution_order"] == ["merge", "redact", "sha256"]
        assert len(result["sha256"]) == 64
        assert "compare-pdf" in result["transfer_destinations"]

        content = client.get(artifact["content_url"])
        assert content.status_code == 200
        with fitz.open(stream=content.content, filetype="pdf") as document:
            assert "SECRET SALARY" not in document[0].get_text()
            assert "APPENDIX PRIVATE" not in document[1].get_text()

        transfer = client.post(
            f"/api/workflows/{workflow_id}/transfer",
            data={
                "artifact_id": artifact["artifact_id"],
                "comparison_artifact_id": original["artifact_id"],
                "destination": "compare-pdf",
                "source_feature": "redact",
            },
        )
        assert transfer.status_code == 200, transfer.text
        compared = client.post(
            "/api/security/compare-pdf-summary",
            data={
                "left_workflow_id": workflow_id,
                "left_artifact_id": original["artifact_id"],
                "right_workflow_id": workflow_id,
                "right_artifact_id": artifact["artifact_id"],
            },
        )
        assert compared.status_code == 200, compared.text
        assert compared.json()["different_pages"] >= 1

    if workflow_id:
        workflow_store.delete(workflow_id)


def test_optional_failure_preserves_successful_redacted_artifact(
    tmp_path: Path,
    monkeypatch,
):
    source = _sensitive_pdf(tmp_path / "source.pdf")
    workflow_id = None

    def fail_compression(*args, **kwargs):
        raise CompressionError("Ghostscript intentionally unavailable")

    monkeypatch.setattr("backend.api.routers.workflows.compress_preset", fail_compression)
    with TestClient(app) as client:
        started = client.post(
            "/api/workflows/redact/start",
            files={"file": _upload(source)},
        ).json()
        workflow_id = started["workflow"]["workflow_id"]
        artifact = started["artifact"]
        marks = client.post(
            f"/api/workflows/{workflow_id}/redact/search",
            data={"artifact_id": artifact["artifact_id"], "query": "SECRET"},
        ).json()["matches"]
        response = client.post(
            f"/api/workflows/{workflow_id}/redact/execute",
            data={
                "artifact_id": artifact["artifact_id"],
                "redactions_json": json.dumps(marks),
                "compress_mode": "recommended",
            },
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["artifact"]["source_operation"] == "redact"
        assert payload["failures"][0]["step"] == "compress"
        with fitz.open(stream=client.get(payload["artifact"]["content_url"]).content, filetype="pdf") as document:
            assert "SECRET" not in document[0].get_text()

    if workflow_id:
        workflow_store.delete(workflow_id)


def test_redact_frontend_and_transfer_contracts_are_registered():
    root = Path(__file__).resolve().parents[1]
    index = (root / "frontend/pages/main/index.html").read_text(encoding="utf-8")
    features = (root / "frontend/assets/js/core/features.js").read_text(encoding="utf-8")
    panel = (root / "frontend/feature_views/edit_pdf/redact-pdf/panel.html").read_text(encoding="utf-8")
    controller = (root / "frontend/feature_views/edit_pdf/redact-pdf/controller.js").read_text(encoding="utf-8")
    transfer = (root / "frontend/assets/js/core/workflow_transfer.js").read_text(encoding="utf-8")
    organizer = (root / "frontend/feature_views/edit_pdf/organize-pdf/panel.html").read_text(encoding="utf-8")

    organize_position = index.index('data-tool="organize"')
    redact_position = index.index('data-tool="redact"')
    merge_position = index.index('data-tool="merge"')
    assert organize_position < redact_position < merge_position
    assert 'redact: { title: "Redact PDF"' in features
    assert 'id="redactFile" multiple' in panel
    assert 'id="redactPagePrep"' in panel
    assert 'id="redactCanvasStage"' in panel
    assert 'data-redact-tool="text"' in panel
    assert 'id="redactSearchExact"' in panel
    assert 'id="previewRedactPages"' in panel
    assert "SECURE INTEGRATED WORKFLOW" not in panel
    assert 'id="redactApplyBtn"' in panel
    assert "workflowReferenceForFile" in controller
    assert "comparisonArtifactId" in transfer
    assert "maxWidth: targetWidth" in controller
    assert "/redact/select-text" in controller
    assert "openPdfPreview(file)" in controller
    assert "selectedMarkId" in controller
    assert "scrollList: true" in controller
    assert "setSelectedMark" in (root / "frontend/assets/js/core/redact_canvas.js").read_text(encoding="utf-8")
    assert 'data-destination="redact"' in organizer
    assert "input?.isConnected" in (root / "frontend/assets/js/core/file_store.js").read_text(encoding="utf-8")
