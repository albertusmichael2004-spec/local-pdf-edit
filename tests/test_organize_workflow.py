from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import shutil

import fitz
from fastapi.testclient import TestClient
from pypdf import PdfReader

from backend.main import app
from backend.services.workflow_session import workflow_store


def _upload(path: Path, name: str | None = None) -> tuple[str, bytes, str]:
    return name or path.name, path.read_bytes(), "application/pdf"


def test_organize_dropzone_auto_merges_and_reconciles_source_files(
    tmp_path: Path,
    make_pdf,
):
    first = make_pdf(tmp_path / "first.pdf", pages=2, prefix="First")
    second = make_pdf(tmp_path / "second.pdf", pages=1, prefix="Second")
    third = make_pdf(tmp_path / "third.pdf", pages=1, prefix="Third")

    with TestClient(app) as client:
        started = client.post(
            "/api/workflows/organize/start",
            files=[("files", _upload(first)), ("files", _upload(second))],
        )
        assert started.status_code == 200, started.text
        payload = started.json()
        workflow_id = payload["workflow"]["workflow_id"]
        sources = payload["source_artifacts"]
        merged = payload["artifact"]
        assert payload["execution_order"] == ["merge"]
        assert merged["page_count"] == 3
        assert [entry["source_artifact_id"] for entry in merged["page_sources"]] == [
            sources[0]["artifact_id"],
            sources[0]["artifact_id"],
            sources[1]["artifact_id"],
        ]
        assert [entry["file_name"] for entry in merged["page_sources"]] == [
            "first.pdf",
            "first.pdf",
            "second.pdf",
        ]

        removed = client.post(
            f"/api/workflows/{workflow_id}/organize/sources",
            data={"kept_artifact_ids_json": json.dumps([sources[1]["artifact_id"]])},
        )
        assert removed.status_code == 200, removed.text
        removed_payload = removed.json()
        assert removed_payload["execution_order"] == []
        assert removed_payload["artifact"]["page_count"] == 1
        assert removed_payload["artifact"]["page_sources"][0]["file_name"] == "second.pdf"

        added = client.post(
            f"/api/workflows/{workflow_id}/organize/sources",
            data={"kept_artifact_ids_json": json.dumps([sources[1]["artifact_id"]])},
            files=[("files", _upload(third))],
        )
        assert added.status_code == 200, added.text
        added_payload = added.json()
        assert added_payload["execution_order"] == ["merge"]
        assert [entry["file_name"] for entry in added_payload["artifact"]["page_sources"]] == [
            "second.pdf",
            "third.pdf",
        ]

        reordered_sources = added_payload["source_artifacts"]
        reordered = client.post(
            f"/api/workflows/{workflow_id}/organize/sources",
            data={
                "kept_artifact_ids_json": json.dumps([
                    reordered_sources[1]["artifact_id"],
                    reordered_sources[0]["artifact_id"],
                ])
            },
        )
        assert reordered.status_code == 200, reordered.text
        assert [entry["file_name"] for entry in reordered.json()["artifact"]["page_sources"]] == [
            "third.pdf",
            "second.pdf",
        ]


def test_organize_view_uses_multi_file_drop_and_embedded_compression_cards():
    root = Path(__file__).resolve().parents[1]
    panel = (root / "frontend/feature_views/edit_pdf/organize-pdf/panel.html").read_text(encoding="utf-8")
    controller = (root / "frontend/feature_views/edit_pdf/organize-pdf/controller.js").read_text(encoding="utf-8")
    workspace = (root / "frontend/assets/js/core/page_workspace.js").read_text(encoding="utf-8")
    organize_controller = (root / "frontend/feature_views/edit_pdf/organize-pdf/controller.js").read_text(encoding="utf-8")
    preview_modal = (root / "frontend/assets/js/core/pdf_preview_modal.js").read_text(encoding="utf-8")

    assert 'id="organizeFile" multiple' in panel
    assert 'data-append="true"' in panel
    assert "organizeMergeEnabled" not in panel
    assert "organizeMergeEnabled" not in controller
    assert 'value="extreme"' in panel
    assert 'value="recommended"' in panel
    assert 'value="less"' in panel
    assert 'value="custom"' in panel
    assert 'id="organizeCompressOrderIndex">1<' in panel
    assert 'id="organizeProtectOrderIndex">2<' in panel
    assert 'id="organizeHashOrderIndex">3<' in panel
    assert "organizeSourceLegend" in panel
    assert "pageSources" in workspace
    assert "sourceColor" in workspace
    assert "singlePage: true" in workspace
    assert "const pagesToRender = singlePage ? [targetPage]" in preview_modal
    assert "shell.classList.add(\"is-visible\")" in preview_modal
    assert "window.setTimeout(() =>" in preview_modal
    assert "_animateLayout" in workspace
    assert "animate = false" in workspace
    assert "isPureSourceReorder" in organize_controller
    assert "animate: reorderOnly" in organize_controller
    assert 'textContent = "1"' in controller
    assert 'textContent = "2"' in controller
    assert 'textContent = "3"' in controller
    features_css = (root / "frontend/assets/css/features.css").read_text(encoding="utf-8")
    assert ".workflow-addon.compact-addon > .workflow-addon-toggle { margin-right: 34px; }" not in features_css
    assert ".workflow-addon-toggle:focus-visible" in features_css
    assert "workflow-addon-expand" not in panel
    redact_panel = (root / "frontend/feature_views/edit_pdf/redact-pdf/panel.html").read_text(encoding="utf-8")
    assert "workflow-addon-expand" not in redact_panel
    assert "justify-self: center" in features_css


def test_workflow_transfer_uses_one_shared_frontend_state_module():
    root = Path(__file__).resolve().parents[1]
    downloads = (root / "frontend/assets/js/core/downloads.js").read_text(encoding="utf-8")
    transfer = (root / "frontend/assets/js/core/workflow_transfer.js").read_text(encoding="utf-8")
    loader = (root / "frontend/assets/js/core/feature_loader.js").read_text(encoding="utf-8")
    index = (root / "frontend/pages/main/index.html").read_text(encoding="utf-8")
    drag_reorder = (root / "frontend/assets/js/core/drag_reorder.js").read_text(encoding="utf-8")
    components_css = (root / "frontend/assets/css/components.css").read_text(encoding="utf-8")

    canonical_store = 'from "/frontend/assets/js/core/file_store.js"'
    canonical_transfer = 'from "/frontend/assets/js/core/workflow_transfer.js"'
    assert canonical_store in downloads
    assert canonical_store in transfer
    assert canonical_transfer in downloads
    assert canonical_transfer in loader
    assert "file_store.js?v=" not in downloads
    assert "workflow_transfer.js?v=" not in loader
    assert 'Symbol.for("local-pdf-workbench.workflow-reference")' in transfer
    assert '"/frontend/assets/js/core/dropzones.js":"/frontend/assets/js/core/dropzones.js?v=6.6"' in index
    assert '"/frontend/assets/js/core/sortable.js":"/frontend/assets/js/core/sortable.js?v=6.6"' in index
    assert '"/frontend/assets/js/core/image_workspace.js":"/frontend/assets/js/core/image_workspace.js?v=6.6"' in index
    assert "stableReorderKey" in drag_reorder
    assert "reorder-pressed" in drag_reorder
    assert "reorder-drop-pop" in drag_reorder
    assert ".reorder-pressed" in components_css
    assert ".reorder-lifted" in components_css
    assert ".reorder-drop-pop" in components_css
    assert ".pdf-preview-modal.is-visible" in components_css
    assert "@keyframes pdfPreviewShimmer" in components_css
    assert ".reorder-ghost { position: fixed !important;" in components_css
    assert "transform: scale(.94);" in components_css
    assert "transform: scale(.94) rotate" not in components_css
    features_css = (root / "frontend/assets/css/features.css").read_text(encoding="utf-8")
    assert "page-editor-card.reorder-lifted .page-editor-page" in features_css
    assert "page-editor-card.reorder-lifted .page-editor-page { cursor: grabbing; transform: translateY(-3px);" in features_css

    destination_controllers = {
        "split": root / "frontend/feature_views/quick_tools/split/controller.js",
        "extract-pages": root / "frontend/feature_views/edit_pdf/extract-pages/controller.js",
        "watermark": root / "frontend/feature_views/edit_pdf/add-watermark/controller.js",
        "crop": root / "frontend/feature_views/edit_pdf/crop-pdf/controller.js",
        "ocr": root / "frontend/feature_views/edit_pdf/ocr-pdf/controller.js",
    }
    for destination, path in destination_controllers.items():
        source = path.read_text(encoding="utf-8")
        assert 'from "/frontend/assets/js/core/downloads.js"' in source, destination
        assert "formWithSingleFile" in source or "bindSimpleDownload" in source, destination


def test_shell_navigation_reset_and_bilingual_ui_contract():
    root = Path(__file__).resolve().parents[1]
    index = (root / "frontend/pages/main/index.html").read_text(encoding="utf-8")
    loader = (root / "frontend/assets/js/core/feature_loader.js").read_text(encoding="utf-8")
    i18n = (root / "frontend/assets/js/core/i18n.js").read_text(encoding="utf-8")

    assert "QUICK TOOLS" not in index
    assert 'id="languageSelect"' in index
    assert 'id="sidebarScroll"' in index
    assert 'id="sidebarScroll">\n<nav' in index
    app_shell = (root / "frontend/pages/main/app_shell.js").read_text(encoding="utf-8")
    assert "preservedScrollTop" in app_shell
    assert "freezeContentLayer" in app_shell
    assert "sidebarContent.style.minWidth" in app_shell
    layout_css = (root / "frontend/assets/css/layout.css").read_text(encoding="utf-8")
    assert ".language-switcher select option { color: #172033; background: #fff; }" in layout_css
    assert ".language-switcher select option:checked { color: #fff; background: #2169d1; }" in layout_css
    assert ".sidebar-scroll {" in layout_css
    assert "--sidebar-gutter: 18px" in layout_css
    assert "padding-left: var(--sidebar-gutter)" in layout_css
    assert "transform: translateX(0)" in layout_css
    assert "clip-path: inset(0 100% 0 0)" in layout_css
    assert 'data-tool="merge">Merge PDF' in index
    assert 'data-tool="split">Split PDF' in index
    assert 'data-tool="organize">Organize PDF' in index
    assert 'data-i18n-badge="nav.recommended"' in index
    assert 'data-tool="media-converter">Media Converter' in index
    assert 'data-tool="media-converter">Media Converter</button>' in index
    assert "nav-tool-featured\" data-badge" in index
    assert "resetAllFiles" in loader
    assert "window.location.assign" not in loader
    assert "clearPendingWorkflowTransfer" in loader
    assert '"createAnother"' in i18n
    assert '"language.indonesian"' in i18n


def test_organize_workflow_merges_executes_and_transfers_by_artifact_id(
    tmp_path: Path,
    make_pdf,
    monkeypatch,
):
    source = make_pdf(tmp_path / "source.pdf", pages=2)
    appendix = make_pdf(tmp_path / "appendix.pdf", pages=1, prefix="Appendix")

    with TestClient(app) as client:
        started = client.post(
            "/api/workflows/organize/start",
            files={"file": _upload(source)},
        )
        assert started.status_code == 200, started.text
        start_payload = started.json()
        workflow_id = start_payload["workflow"]["workflow_id"]
        original = start_payload["artifact"]
        assert original["page_count"] == 2
        assert len(set(original["page_ids"])) == 2

        merged_response = client.post(
            f"/api/workflows/{workflow_id}/organize/merge",
            data={"base_artifact_id": original["artifact_id"]},
            files=[("files", _upload(appendix))],
        )
        assert merged_response.status_code == 200, merged_response.text
        merged = merged_response.json()["artifact"]
        assert merged["page_count"] == 3
        assert merged["page_ids"][:2] == original["page_ids"]

        plan = [
            {
                "page_id": merged["page_ids"][2],
                "source_page": 3,
                "source_page_id": merged["page_ids"][2],
                "rotation": 90,
                "width_pt": 400,
                "height_pt": 600,
            },
            {
                "page_id": "blank_test_page",
                "source_page": None,
                "source_page_id": None,
                "rotation": 0,
                "width_pt": 400,
                "height_pt": 600,
            },
            {
                "page_id": merged["page_ids"][0],
                "source_page": 1,
                "source_page_id": merged["page_ids"][0],
                "rotation": 0,
                "width_pt": 400,
                "height_pt": 600,
            },
        ]
        executed = client.post(
            f"/api/workflows/{workflow_id}/organize/execute",
            data={
                "artifact_id": merged["artifact_id"],
                "plan_json": json.dumps(plan),
                "generate_sha256": "true",
            },
        )
        assert executed.status_code == 200, executed.text
        result = executed.json()
        artifact = result["artifact"]
        assert result["execution_order"] == ["merge", "organize", "sha256"]
        assert len(result["sha256"]) == 64
        assert artifact["page_ids"] == [
            merged["page_ids"][2],
            "blank_test_page",
            merged["page_ids"][0],
        ]

        content = client.get(artifact["content_url"])
        assert content.status_code == 200
        with fitz.open(stream=content.content, filetype="pdf") as document:
            assert document.page_count == 3
            assert document[0].rotation == 90
            assert "Appendix 1" in document[0].get_text()
            assert document[1].get_text().strip() == ""
            assert "Page 1" in document[2].get_text()

        prepared = client.post(
            f"/api/workflows/{workflow_id}/transfer",
            data={"artifact_id": artifact["artifact_id"], "destination": "extract-pages"},
        )
        assert prepared.status_code == 200
        extracted = client.post(
            "/api/edit/extract-pages",
            data={
                "workflow_id": workflow_id,
                "artifact_id": artifact["artifact_id"],
                "pages": "1",
            },
        )
        assert extracted.status_code == 200, extracted.text
        assert len(PdfReader(BytesIO(extracted.content)).pages) == 1

        shared_reference = {
            "workflow_id": workflow_id,
            "artifact_id": artifact["artifact_id"],
        }
        split = client.post(
            "/api/split",
            data={
                **shared_reference,
                "mode": "range",
                "ranges": "1-2",
                "merge_ranges": "true",
            },
        )
        assert split.status_code == 200, split.text
        assert len(PdfReader(BytesIO(split.content)).pages) == 2

        watermarked = client.post(
            "/api/edit/watermark",
            data={
                **shared_reference,
                "rules_json": json.dumps([{
                    "text": "WORKFLOW QA",
                    "pages": [1],
                    "opacity": 0.3,
                    "font_size": 18,
                    "rotation": 0,
                    "font_key": "arial",
                }]),
            },
        )
        assert watermarked.status_code == 200, watermarked.text
        with fitz.open(stream=watermarked.content, filetype="pdf") as document:
            assert "WORKFLOW QA" in document[0].get_text().replace("\xa0", " ")

        cropped = client.post(
            "/api/edit/crop",
            data={
                **shared_reference,
                "crop_plan_json": json.dumps({
                    "1": {"left_mm": 1, "top_mm": 1, "right_mm": 1, "bottom_mm": 1}
                }),
            },
        )
        assert cropped.status_code == 200, cropped.text
        assert len(PdfReader(BytesIO(cropped.content)).pages) == 3

        def fake_ocr(input_path, output_path, language, dpi):
            shutil.copy2(input_path, output_path)
            return len(PdfReader(str(input_path)).pages)

        monkeypatch.setattr("backend.api.routers.edit_pdf.ocr.ocr_pdf", fake_ocr)
        ocr = client.post(
            "/api/edit/ocr",
            data={**shared_reference, "language": "eng", "dpi": "150"},
        )
        assert ocr.status_code == 200, ocr.text
        assert len(PdfReader(BytesIO(ocr.content)).pages) == 3

        finished = client.delete(f"/api/workflows/{workflow_id}")
        assert finished.json() == {"status": "finished", "removed": True}
        assert client.get(artifact["content_url"]).status_code == 400


def test_organize_workflow_rejects_stale_page_identity_and_protected_transfer(
    tmp_path: Path,
    make_pdf,
):
    source = make_pdf(tmp_path / "source.pdf", pages=1)
    workflow_id = None
    with TestClient(app) as client:
        started = client.post(
            "/api/workflows/organize/start",
            files={"file": _upload(source)},
        ).json()
        workflow_id = started["workflow"]["workflow_id"]
        original = started["artifact"]
        stale_plan = [{
            "page_id": "instance_1",
            "source_page": 1,
            "source_page_id": "stale-page-id",
            "rotation": 0,
        }]
        stale = client.post(
            f"/api/workflows/{workflow_id}/organize/execute",
            data={
                "artifact_id": original["artifact_id"],
                "plan_json": json.dumps(stale_plan),
            },
        )
        assert stale.status_code == 400
        assert "page identity" in stale.json()["detail"]

        valid_plan = [{
            "page_id": original["page_ids"][0],
            "source_page": 1,
            "source_page_id": original["page_ids"][0],
            "rotation": 0,
        }]
        protected = client.post(
            f"/api/workflows/{workflow_id}/organize/execute",
            data={
                "artifact_id": original["artifact_id"],
                "plan_json": json.dumps(valid_plan),
                "protect_password": "secret",
                "generate_sha256": "true",
            },
        )
        assert protected.status_code == 200, protected.text
        payload = protected.json()
        assert payload["transfer_destinations"] == []
        reader = PdfReader(BytesIO(client.get(payload["artifact"]["content_url"]).content))
        assert reader.is_encrypted
        denied = client.post(
            f"/api/workflows/{workflow_id}/transfer",
            data={"artifact_id": payload["artifact"]["artifact_id"], "destination": "crop"},
        )
        assert denied.status_code == 400
        assert "unlocked" in denied.json()["detail"]

    if workflow_id:
        workflow_store.delete(workflow_id)
