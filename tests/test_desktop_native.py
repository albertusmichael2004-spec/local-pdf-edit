from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace
import time
import zipfile

from fastapi.testclient import TestClient

from backend.api.routers import desktop_native
from backend.main import app


PASSWORD = "correct-horse-battery-staple"


def test_windows_dialog_uses_sta_powershell_and_returns_utf8_path(monkeypatch, tmp_path: Path):
    powershell = tmp_path / "powershell.exe"
    powershell.write_bytes(b"")
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return SimpleNamespace(returncode=0, stdout="C:\\Dokumen\\contoh.pdf", stderr="")

    monkeypatch.setattr(desktop_native, "_windows_powershell", lambda: powershell)
    monkeypatch.setattr(desktop_native.subprocess, "run", fake_run)

    selected = desktop_native._run_windows_dialog(
        "dialog-script",
        {"LPW_DIALOG_TITLE": "Choose a local file"},
    )

    assert selected == "C:\\Dokumen\\contoh.pdf"
    assert captured["command"][:5] == [
        str(powershell), "-NoLogo", "-NoProfile", "-NonInteractive", "-STA",
    ]
    assert "shell" not in captured["kwargs"]
    assert captured["kwargs"]["env"]["LPW_DIALOG_TITLE"] == "Choose a local file"


def test_http_file_and_folder_pickers_return_real_path_metadata(tmp_path: Path, monkeypatch):
    source = tmp_path / "document.bin"
    source.write_bytes(b"desktop bridge")
    folder = tmp_path / "folder"
    folder.mkdir()
    monkeypatch.setattr(
        desktop_native,
        "_choose_file_dialog",
        lambda **_kwargs: str(source),
    )
    monkeypatch.setattr(
        desktop_native,
        "_choose_folder_dialog",
        lambda **_kwargs: str(folder),
    )

    with TestClient(app) as client:
        file_response = client.post("/api/desktop-native/choose/security-file", json={})
        folder_response = client.post("/api/desktop-native/choose/hash-folder", json={})

    assert file_response.status_code == 200
    assert file_response.json() == {
        "path": str(source.resolve()),
        "name": source.name,
        "bytes": len(b"desktop bridge"),
        "kind": "file",
    }
    assert folder_response.status_code == 200
    assert folder_response.json() == {
        "path": str(folder.resolve()),
        "name": folder.name,
        "kind": "folder",
    }


def test_http_picker_cancel_returns_null(monkeypatch):
    monkeypatch.setattr(desktop_native, "_choose_file_dialog", lambda **_kwargs: None)

    with TestClient(app) as client:
        response = client.post("/api/desktop-native/choose/archive", json={})

    assert response.status_code == 200
    assert response.json() is None


def test_path_operations_reject_relative_missing_and_non_json_paths(tmp_path: Path):
    source = tmp_path / "input.txt"
    source.write_text("content", encoding="utf-8")

    with TestClient(app) as client:
        relative = client.post("/api/desktop-native/hash/start", json={"path": "input.txt"})
        missing = client.post(
            "/api/desktop-native/hash/start",
            json={"path": str(tmp_path / "missing.txt")},
        )
        non_json = client.post(
            "/api/desktop-native/secure-all-in-one",
            data={"path": str(source), "password": PASSWORD},
        )

    assert relative.status_code == 400
    assert "absolute" in relative.json()["detail"]
    assert missing.status_code == 400
    assert "does not exist" in missing.json()["detail"]
    assert non_json.status_code in {415, 422}


def test_extract_archive_http_bridge_uses_existing_service(tmp_path: Path):
    archive_path = tmp_path / "bundle.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("nested/result.txt", b"extracted through HTTP")

    with TestClient(app) as client:
        response = client.post(
            "/api/desktop-native/extract-archive",
            json={"path": str(archive_path), "same_folder": True, "password": ""},
        )

    assert response.status_code == 200
    payload = response.json()
    destination = Path(payload["path"])
    assert destination.parent == tmp_path.resolve()
    assert payload["files"] == 1
    assert (destination / "nested" / "result.txt").read_bytes() == b"extracted through HTTP"


def test_secure_all_in_one_http_bridge_encrypts_local_file(tmp_path: Path):
    source = tmp_path / "private.txt"
    source.write_bytes(b"private local content")

    with TestClient(app) as client:
        response = client.post(
            "/api/desktop-native/secure-all-in-one",
            json={
                "path": str(source),
                "password": PASSWORD,
                "delete_original": False,
                "reduce_size": False,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert Path(payload["path"]).is_file()
    assert payload["original_trashed"] is False
    assert source.is_file()


def test_hash_path_http_job_can_be_polled_to_completion(tmp_path: Path):
    source = tmp_path / "hash-folder"
    source.mkdir()
    first = b"first file"
    second = b"second file"
    (source / "first.txt").write_bytes(first)
    (source / "second.bin").write_bytes(second)

    with TestClient(app) as client:
        started = client.post(
            "/api/desktop-native/hash/start",
            json={"path": str(source)},
        )
        assert started.status_code == 202
        job_id = started.json()["job_id"]
        deadline = time.monotonic() + 10
        while True:
            polled = client.get(f"/api/desktop-native/hash/jobs/{job_id}")
            assert polled.status_code == 200
            job = polled.json()
            if job["status"] != "running":
                break
            assert time.monotonic() < deadline
            time.sleep(0.01)

    assert job["status"] == "complete"
    assert job["progress"]["status"] == "complete"
    assert job["progress"]["percent"] == 100
    assert job["result"]["kind"] == "folder"
    assert job["result"]["files"] == 2
    assert job["result"]["bytes"] == len(first) + len(second)
    assert len(job["result"]["sha256"]) == hashlib.sha256().digest_size * 2


def test_native_api_javascript_has_http_fallback_and_progress_messages():
    source = (
        Path(__file__).parents[1] / "frontend" / "assets" / "js" / "core" / "native_api.js"
    ).read_text(encoding="utf-8")

    assert 'const BASE_URL = "/api/desktop-native"' in source
    assert 'postJson("/hash/start", { path })' in source
    assert 'type: "pdf-workbench-native-hash-progress"' in source
    assert "injectedNativeApi() || httpNativeApi" in source
