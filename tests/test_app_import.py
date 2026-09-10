from backend.main import app
from backend.core import preferences
from fastapi.testclient import TestClient
import multiprocessing
import threading
from urllib.error import HTTPError
from urllib.request import urlopen

import desktop


def test_desktop_startup_cache_marker_is_versioned(tmp_path, monkeypatch):
    cache_file = tmp_path / "startup-cache.json"
    monkeypatch.setattr(desktop, "_startup_cache_file", lambda: cache_file)

    assert desktop._startup_cache_is_warm() is False
    assert desktop.DesktopApi().mark_startup_cache(desktop.STARTUP_CACHE_VERSION) is True
    assert desktop._startup_cache_is_warm() is True
    assert desktop.DesktopApi().mark_startup_cache("stale-version") is False


def test_startup_cache_write_failure_never_becomes_startup_failure(monkeypatch):
    def deny_cache_file():
        raise PermissionError("cache is unavailable")

    monkeypatch.setattr(desktop, "_startup_cache_file", deny_cache_file)

    assert desktop._mark_startup_cache_ready() is False
    assert desktop.DesktopApi().mark_startup_cache(desktop.STARTUP_CACHE_VERSION) is False


def test_app_routes_are_registered():
    schema = app.openapi()
    paths = set(schema["paths"].keys())

    assert "/api/edit/compress" in paths
    assert "/api/convert/jpg-to-pdf" in paths
    assert "/api/convert/pdf-to-word" in paths
    assert "/api/security/compare-pdf-summary" in paths
    assert "/api/media/probe" in paths
    assert "/api/media/capabilities" in paths
    assert "/api/compress/media" in paths
    assert "/api/compress/images" in paths
    assert "/api/convert/video" in paths
    assert "/api/convert/audio" in paths
    assert "/api/convert/images" in paths
    assert "/api/convert/ebook" in paths
    assert "/api/document-security/sha256" in paths
    assert "/api/workspace/reset" in paths
    assert "/api/workflows/organize/start" in paths
    assert "/api/workflows/{workflow_id}/organize/execute" in paths


def test_workspace_reset_cleans_orphaned_workspaces_without_error():
    with TestClient(app) as client:
        response = client.post("/api/workspace/reset")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "reset"
    assert isinstance(payload["removed_workspaces"], int)
    assert isinstance(payload["removed_workflows"], int)


def test_health_reports_no_application_upload_cap():
    with TestClient(app) as client:
        payload = client.get("/api/health").json()

    assert payload["upload_limit"] is None
    assert payload["max_archive_output_mb"] is None
    assert "max_file_mb" not in payload


def test_language_preference_survives_api_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(preferences, "persistent_data_root", lambda: tmp_path)
    with TestClient(app) as client:
        assert client.get("/api/preferences/language").json() == {"language": "en"}
        saved = client.put("/api/preferences/language", json={"language": "id"})
        assert saved.status_code == 200
        assert saved.json() == {"language": "id"}
        assert client.get("/api/preferences/language").json() == {"language": "id"}


def test_desktop_engine_runs_outside_ui_process_and_serves_static_shell():
    port = desktop._free_local_port()
    context = multiprocessing.get_context("spawn")
    progress_reader, progress_writer = context.Pipe(duplex=False)
    process = context.Process(target=desktop._run_server_process, args=(port, progress_writer))
    process.start()
    progress_writer.close()
    try:
        desktop._wait_for_port(port, timeout=15, process=process)
        progress_updates = []
        while progress_reader.poll():
            progress_updates.append(progress_reader.recv())
        with urlopen(f"http://127.0.0.1:{port}/", timeout=5) as response:
            html = response.read().decode("utf-8")
        assert response.status == 200
        assert "Local PDF Workbench" in html
        assert process.is_alive()
        assert [percent for percent, _label in progress_updates] == [5, 70, 98]
    finally:
        progress_reader.close()
        if process.is_alive():
            process.terminate()
        process.join(timeout=5)


def test_desktop_gateway_serves_ui_before_engine_and_proxies_after_ready():
    gateway_port = desktop._free_local_port()
    engine_port = desktop._free_local_port()
    gateway = desktop._GatewayServer(("127.0.0.1", gateway_port), desktop._GatewayHandler)
    ui_ready = threading.Event()
    gateway.ui_ready_event = ui_ready
    gateway_thread = threading.Thread(target=gateway.serve_forever, daemon=True)
    gateway_thread.start()
    process = None
    try:
        with urlopen(f"http://127.0.0.1:{gateway_port}/", timeout=5) as response:
            assert response.status == 200
            assert b"Local PDF Workbench" in response.read()
        assert ui_ready.wait(timeout=1)
        try:
            urlopen(f"http://127.0.0.1:{gateway_port}/api/health", timeout=5)
            raise AssertionError("API should report startup until the engine is connected.")
        except HTTPError as exc:
            assert exc.code == 503

        context = multiprocessing.get_context("spawn")
        process = context.Process(target=desktop._run_server_process, args=(engine_port,))
        process.start()
        desktop._wait_for_port(engine_port, timeout=15, process=process)
        gateway.engine_port = engine_port
        with urlopen(f"http://127.0.0.1:{gateway_port}/api/health", timeout=30) as response:
            payload = response.read()
        assert response.status == 200
        assert b'"upload_limit":null' in payload
    finally:
        gateway.shutdown()
        gateway.server_close()
        gateway_thread.join(timeout=5)
        if process is not None and process.is_alive():
            process.terminate()
            process.join(timeout=5)


def test_desktop_prefers_full_browser_shell(monkeypatch):
    calls = []
    monkeypatch.setattr(desktop, "_browser_main_impl", lambda: calls.append("browser"))
    monkeypatch.setattr(desktop, "_pywebview_main_impl", lambda: calls.append("webview"))

    desktop._main_impl()

    assert calls == ["browser"]


def test_desktop_falls_back_to_webview_when_browser_is_unavailable(monkeypatch):
    calls = []

    def unavailable():
        calls.append("browser")
        raise RuntimeError("No full browser")

    monkeypatch.setattr(desktop, "_browser_main_impl", unavailable)
    monkeypatch.setattr(desktop, "_pywebview_main_impl", lambda: calls.append("webview"))

    desktop._main_impl()

    assert calls == ["browser", "webview"]


def test_browser_window_reapplies_launcher_icon_until_chromium_closes(tmp_path, monkeypatch):
    profile = tmp_path / "browser-profile"
    profile.mkdir()
    icon_path = tmp_path / "app.ico"
    icon_path.write_bytes(b"icon")
    process_snapshots = iter(([101], [101], []))
    applied = []
    destroyed = []

    monkeypatch.setattr(
        desktop,
        "_browser_profile_processes",
        lambda _profile: list(next(process_snapshots)),
    )
    monkeypatch.setattr(desktop, "_browser_window_handles", lambda process_ids: [501])
    monkeypatch.setattr(desktop, "_load_windows_icon", lambda path: 9001)
    monkeypatch.setattr(
        desktop,
        "_set_windows_window_icon",
        lambda hwnd, icon: applied.append((hwnd, icon)),
    )
    monkeypatch.setattr(desktop, "_destroy_windows_icon", destroyed.append)
    monkeypatch.setattr(desktop.time, "sleep", lambda _seconds: None)

    class BrowserProcess:
        @staticmethod
        def poll():
            return None

    desktop._wait_for_browser_window(BrowserProcess(), profile, icon_path)

    assert applied == [(501, 9001), (501, 9001)]
    assert destroyed == [9001]
