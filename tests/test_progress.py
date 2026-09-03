from fastapi.testclient import TestClient

from backend.core.progress import (
    bind_progress,
    registry,
    report_fraction,
    reset_progress,
)
from backend.main import app


def test_progress_registry_tracks_real_fraction():
    job_id = "unit-progress-fraction"
    registry.start(job_id, "Watermarking PDF")
    token = bind_progress(job_id)
    try:
        report_fraction("Applying watermark to pages", 4, 10, 20, 90)
    finally:
        reset_progress(token)

    state = registry.snapshot(job_id)
    assert state["stage"] == "Applying watermark to pages"
    assert state["percent"] == 48
    assert state["completed"] == 4
    assert state["total"] == 10


def test_upload_operation_exposes_progress_endpoint():
    job_id = "api-sha-progress"
    with TestClient(app) as client:
        response = client.post(
            "/api/document-security/sha256",
            headers={"X-Progress-ID": job_id},
            files={"file": ("sample.bin", b"progress payload", "application/octet-stream")},
        )
        progress = client.get(f"/api/progress/{job_id}")

    assert response.status_code == 200
    assert response.headers["x-progress-id"] == job_id
    assert progress.json()["status"] == "complete"
    assert progress.json()["percent"] == 100
    assert progress.json()["operation"] == "Calculating SHA-256"
