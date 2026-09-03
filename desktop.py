from __future__ import annotations

import inspect
import html
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import multiprocessing
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

APP_TITLE = "Local PDF Workbench"
APP_ID = "LocalPDFWorkbench.Desktop"
APP_GATEWAY_PORT = 17842
STARTUP_CACHE_VERSION = "6.0"
_ELEVATION_MARKER = "LOCAL_PDF_WORKBENCH_ELEVATED"
SPLASH_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Local PDF Workbench</title>
<style>
  :root { color-scheme: dark; font-family: "Segoe UI", sans-serif; }
  * { box-sizing: border-box; }
  body { margin: 0; min-height: 100vh; display: grid; place-items: center;
    background: radial-gradient(circle at 50% 35%, #243b65 0, #121d32 45%, #0b1220 100%);
    color: #f7f9ff; }
  main { width: min(520px, calc(100vw - 48px)); display: grid; justify-items: center; gap: 18px; text-align: center; }
  .mark { width: 72px; height: 72px; display: grid; place-items: center; border-radius: 20px;
    background: linear-gradient(145deg, #ff6b5e, #dd3347); box-shadow: 0 18px 46px #0008;
    font-size: 27px; font-weight: 800; letter-spacing: -2px; }
  h1 { margin: 0; font-size: 24px; font-weight: 650; letter-spacing: -.3px; }
  p { min-height: 21px; margin: -8px 0 2px; color: #aebbd3; font-size: 14px; }
  .loader { width: 100%; height: 8px; overflow: hidden; border-radius: 99px; background: #ffffff1c;
    box-shadow: inset 0 1px 2px #0007; }
  .loader > span { display: block; width: 2%; height: 100%; border-radius: inherit;
    background: linear-gradient(90deg, #ff655b, #ffb36b); transition: width .22s ease; }
  .meta { width: 100%; display: flex; justify-content: space-between; color: #8492aa; font-size: 12px; }
</style>
</head>
<body><main><div class="mark">PDF</div><h1>Local PDF Workbench</h1>
<p id="startupLabel">Preparing local workspace…</p>
<div class="loader" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="2">
  <span id="startupBar"></span>
</div>
<div class="meta"><span>Loading all features locally</span><span id="startupPercent">2%</span></div>
</main>
<script>
window.updateStartupProgress = (percent, label) => {
  const value = Math.max(2, Math.min(100, Number(percent) || 2));
  document.querySelector('#startupBar').style.width = `${value}%`;
  document.querySelector('.loader').setAttribute('aria-valuenow', String(value));
  document.querySelector('#startupPercent').textContent = `${Math.round(value)}%`;
  document.querySelector('#startupLabel').textContent = label || 'Preparing local workspace…';
};
</script></body>
</html>"""


def _free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_port(
    port: int,
    timeout: float | None = 10.0,
    process: multiprocessing.Process | None = None,
) -> None:
    deadline = time.monotonic() + timeout if timeout is not None else None
    while deadline is None or time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                return
        except OSError:
            if process is not None and not process.is_alive():
                raise RuntimeError(
                    f"Local PDF engine exited during startup (exit code {process.exitcode})."
                )
            time.sleep(0.08)
    raise RuntimeError("Local PDF server did not start in time.")


def _set_windows_app_identity() -> None:
    if os.name != "nt":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass


def _local_app_data() -> Path:
    root = os.environ.get("LOCALAPPDATA")
    if root:
        return Path(root) / "LocalPDFWorkbench"
    return Path.home() / ".local-pdf-workbench"


def _startup_cache_file() -> Path:
    return _local_app_data() / "startup-cache.json"


def _startup_cache_is_warm() -> bool:
    try:
        payload = json.loads(_startup_cache_file().read_text(encoding="utf-8"))
        return payload.get("version") == STARTUP_CACHE_VERSION
    except (OSError, ValueError, TypeError):
        return False


def _mark_startup_cache_ready() -> bool:
    try:
        cache_file = _startup_cache_file()
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(
            json.dumps({"version": STARTUP_CACHE_VERSION, "ready": True}),
            encoding="utf-8",
        )
        return True
    except OSError:
        # Cache persistence is an optimization, never a startup requirement.
        return False


def _fatal_message(message: str) -> None:
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, APP_TITLE, 0x10)
            return
        except Exception:
            pass
    print(message, file=sys.stderr)


def _is_windows_administrator() -> bool:
    """Return the current token's administrator status without importing GUI code."""
    if os.name != "nt":
        return True
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        # If Windows cannot answer (for example during a restricted test host),
        # keep the normal startup path usable. The packaged executable also has
        # a requireAdministrator manifest as a second line of enforcement.
        return True


def _ensure_windows_administrator() -> bool:
    """Request elevation for source-mode launches and report whether we relaunched.

    PyInstaller builds carry a ``requireAdministrator`` manifest. Source-mode
    launches use ShellExecute's ``runas`` verb because a Python interpreter does
    not inherit an application manifest from the module it executes.
    """
    if os.name != "nt" or getattr(sys, "frozen", False):
        return False
    if _is_windows_administrator():
        return False
    if os.environ.get(_ELEVATION_MARKER) == "1":
        raise RuntimeError("Local PDF Workbench could not obtain administrator access.")

    try:
        import ctypes

        working_directory = str(Path(__file__).resolve().parent)
        result = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            sys.executable,
            "-I -m desktop",
            working_directory,
            1,
        )
    except Exception as exc:
        raise RuntimeError("Windows elevation request could not be started.") from exc
    if int(result) <= 32:
        if int(result) in {5, 1223}:
            raise RuntimeError("Administrator access was cancelled, so Local PDF Workbench did not start.")
        raise RuntimeError(f"Windows elevation request failed (code {int(result)}).")
    return True


def _app_icon() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    root = Path(bundle_root) if bundle_root else Path(__file__).resolve().parent
    return root / "frontend" / "assets" / "images" / "app.ico"


def _frontend_root() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    root = Path(bundle_root) if bundle_root else Path(__file__).resolve().parent
    return root / "frontend"


class _LazyBackendApp:
    """Start HTTP immediately and import the processing stack on first API use."""

    def __init__(self, progress_pipe=None) -> None:
        self.frontend = _frontend_root().resolve()
        self._app = None
        self._load_lock = threading.Lock()
        self._load_started = False
        self._load_done = threading.Event()
        self._load_error: BaseException | None = None
        self._progress_pipe = progress_pipe

    def _load_backend_worker(self) -> None:
        try:
            _emit_startup_progress(
                self._progress_pipe,
                82,
                "Loading application features…",
            )
            from backend.main import app

            self._app = app
            _mark_startup_cache_ready()
            _emit_startup_progress(
                self._progress_pipe,
                100,
                "Application features are ready.",
            )
        except BaseException as exc:
            self._load_error = exc
        finally:
            self._load_done.set()

    def start_backend_load(self) -> None:
        with self._load_lock:
            if self._load_started:
                return
            self._load_started = True
            threading.Thread(
                target=self._load_backend_worker,
                name="pdf-workbench-feature-loader",
                daemon=True,
            ).start()

    def load_backend(self):
        self.start_backend_load()
        self._load_done.wait()
        if self._load_error is not None:
            raise RuntimeError("Application features failed to load.") from self._load_error
        return self._app

    async def _startup_status(self, send) -> None:
        self.start_backend_load()
        if self._load_error is not None:
            payload = {
                "status": "error",
                "detail": str(self._load_error) or self._load_error.__class__.__name__,
            }
        elif self._load_done.is_set() and self._app is not None:
            payload = {"status": "ready"}
        else:
            payload = {"status": "loading"}
        body = json.dumps(payload).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"content-length", str(len(body)).encode("ascii")),
                (b"cache-control", b"no-store"),
            ],
        })
        await send({"type": "http.response.body", "body": body})

    async def _lifespan(self, receive, send) -> None:
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return

    async def _static(self, scope, send) -> None:
        path = scope.get("path", "/")
        relative = "pages/main/index.html" if path == "/" else path.removeprefix("/frontend/")
        candidate = (self.frontend / relative).resolve()
        try:
            candidate.relative_to(self.frontend)
        except ValueError:
            candidate = self.frontend / "__not_found__"
        if scope.get("method") not in {"GET", "HEAD"}:
            status, body = 405, b"Method not allowed"
        elif not candidate.is_file():
            status, body = 404, b"Not found"
        else:
            status, body = 200, candidate.read_bytes()
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        headers = [
            (b"content-type", content_type.encode("ascii") + (b"; charset=utf-8" if content_type.startswith("text/") else b"")),
            (b"content-length", str(len(body)).encode("ascii")),
        ]
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": b"" if scope.get("method") == "HEAD" else body})

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "lifespan":
            await self._lifespan(receive, send)
            return
        path = scope.get("path", "/")
        if scope["type"] == "http" and (path == "/" or path.startswith("/frontend/")):
            await self._static(scope, send)
            return
        if scope["type"] == "http" and path == "/api/desktop-startup":
            await self._startup_status(send)
            return
        await self.load_backend()(scope, receive, send)


class _GatewayServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler_class) -> None:
        super().__init__(address, handler_class)
        self.frontend = _frontend_root().resolve()
        self.engine_port: int | None = None
        self.ui_ready_event: threading.Event | None = None


class _GatewayHandler(BaseHTTPRequestHandler):
    """Serve the UI immediately, then proxy API traffic to the isolated engine."""

    protocol_version = "HTTP/1.0"

    def log_message(self, _format: str, *_args) -> None:
        return

    def do_HEAD(self) -> None:
        self._dispatch()

    def do_GET(self) -> None:
        self._dispatch()

    def do_POST(self) -> None:
        self._dispatch()

    def do_PUT(self) -> None:
        self._dispatch()

    def do_DELETE(self) -> None:
        self._dispatch()

    @property
    def gateway(self) -> _GatewayServer:
        return self.server  # type: ignore[return-value]

    def _dispatch(self) -> None:
        if self.path == "/api" or self.path.startswith("/api/"):
            self._proxy_api()
        else:
            self._serve_static()

    def _serve_static(self) -> None:
        request_path = self.path.split("?", 1)[0]
        relative = "pages/main/index.html" if request_path == "/" else request_path.removeprefix("/frontend/")
        candidate = (self.gateway.frontend / relative).resolve()
        try:
            candidate.relative_to(self.gateway.frontend)
        except ValueError:
            candidate = self.gateway.frontend / "__not_found__"
        if self.command not in {"GET", "HEAD"}:
            self._plain_response(405, b"Method not allowed", "text/plain; charset=utf-8")
            return
        if not candidate.is_file():
            self._plain_response(404, b"Not found", "text/plain; charset=utf-8")
            return
        body = candidate.read_bytes()
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in {"application/javascript", "application/json"}:
            content_type += "; charset=utf-8"
        self._plain_response(200, body, content_type)
        # The top-level UI document has been delivered to WebView2. Give the
        # renderer 0.75 seconds to paint it before starting the heavy engine.
        if (
            request_path == "/"
            and self.gateway.ui_ready_event is not None
        ):
            self.gateway.ui_ready_event.set()

    def _plain_response(self, status: int, body: bytes, content_type: str) -> None:
        request_path = self.path.split("?", 1)[0]
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header(
            "Cache-Control",
            "no-store"
            if request_path == "/" or request_path.startswith("/api")
            else "public, max-age=31536000, immutable",
        )
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _proxy_api(self) -> None:
        port = self.gateway.engine_port
        if port is None:
            self._plain_response(
                503,
                b'{"detail":"The local engine is finishing startup. Retry in a moment."}',
                "application/json; charset=utf-8",
            )
            return
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=60 * 60)
        try:
            connection.putrequest(self.command, self.path, skip_host=True, skip_accept_encoding=True)
            excluded = {"connection", "host", "proxy-connection", "transfer-encoding"}
            for name, value in self.headers.items():
                if name.lower() not in excluded:
                    connection.putheader(name, value)
            connection.putheader("Host", f"127.0.0.1:{port}")
            connection.endheaders()
            remaining = int(self.headers.get("Content-Length", "0") or 0)
            while remaining > 0:
                chunk = self.rfile.read(min(8 * 1024 * 1024, remaining))
                if not chunk:
                    break
                connection.send(chunk)
                remaining -= len(chunk)
            response = connection.getresponse()
            self.send_response(response.status, response.reason)
            hop_headers = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers", "transfer-encoding", "upgrade"}
            for name, value in response.getheaders():
                if name.lower() not in hop_headers:
                    self.send_header(name, value)
            self.end_headers()
            if self.command != "HEAD":
                while chunk := response.read(1024 * 1024):
                    self.wfile.write(chunk)
        except (OSError, http.client.HTTPException) as exc:
            if not self.wfile.closed:
                try:
                    self._plain_response(502, str(exc).encode("utf-8", "replace"), "text/plain; charset=utf-8")
                except OSError:
                    pass
        finally:
            connection.close()


class DesktopApi:
    """Native filesystem operations that require real Windows paths."""

    def __init__(self) -> None:
        self.window = None
        self.ready_event = threading.Event()

    def ui_ready(self):
        self.ready_event.set()
        return True

    def mark_startup_cache(self, version: str):
        if str(version) != STARTUP_CACHE_VERSION:
            return False
        return _mark_startup_cache_ready()

    def report_startup_error(self, message: str):
        log_file = _local_app_data() / "frontend-startup-error.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.write_text(str(message), encoding="utf-8")
        return True

    def _choose(self, file_types: tuple[str, ...]):
        if self.window is None:
            raise RuntimeError("The desktop window is not ready.")
        import webview

        selected = self.window.create_file_dialog(
            webview.FileDialog.OPEN,
            allow_multiple=False,
            file_types=file_types,
        )
        if not selected:
            return None
        path = Path(selected[0]).resolve()
        return {"path": str(path), "name": path.name, "bytes": path.stat().st_size}

    def choose_archive(self):
        return self._choose((
            "Compressed files (*.zip;*.7z;*.rar;*.tar;*.tar.gz;*.tgz;*.tar.bz2;*.tbz2;*.tar.xz;*.txz;*.gz;*.bz2;*.xz;*.cab)",
            "All files (*.*)",
        ))

    def choose_security_file(self):
        return self._choose(("All files (*.*)",))

    def choose_security_folder(self):
        if self.window is None:
            raise RuntimeError("The desktop window is not ready.")
        import webview

        selected = self.window.create_file_dialog(
            webview.FileDialog.FOLDER,
            allow_multiple=False,
        )
        if not selected:
            return None
        path = Path(selected[0]).resolve()
        return {"path": str(path), "name": path.name or str(path), "kind": "folder"}

    def choose_hash_file(self):
        return self._choose(("All files (*.*)",))

    def choose_hash_folder(self):
        if self.window is None:
            raise RuntimeError("The desktop window is not ready.")
        import webview

        selected = self.window.create_file_dialog(
            webview.FileDialog.FOLDER,
            allow_multiple=False,
        )
        if not selected:
            return None
        path = Path(selected[0]).resolve()
        return {"path": str(path), "name": path.name or str(path), "kind": "folder"}

    def hash_security_path(self, source_path: str):
        from backend.services.document_security.hash_file import create_path_hash

        started = time.monotonic()

        def update(completed, total, files_completed, files_total, current_name):
            byte_ratio = completed / total if total else 0
            file_ratio = files_completed / files_total if files_total else 1
            percent = min(99, max(1, round((byte_ratio if total else file_ratio) * 100, 1)))
            payload = {
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
            if self.window is not None:
                try:
                    self.window.evaluate_js(
                        f"window.updateNativeHashProgress?.({json.dumps(payload)});"
                    )
                except Exception:
                    pass

        result = create_path_hash(Path(source_path), update)
        return {
            "name": result.name,
            "bytes": result.bytes,
            "sha256": result.sha256,
            "kind": result.kind,
            "files": result.files,
        }

    def _choose_output_folder(self, initial_folder: Path) -> Path | None:
        if self.window is None:
            raise RuntimeError("The desktop window is not ready.")
        import webview

        selected = self.window.create_file_dialog(
            webview.FileDialog.FOLDER,
            directory=str(initial_folder),
            allow_multiple=False,
        )
        if not selected:
            return None
        return Path(selected[0]).resolve()

    def extract_archive(self, archive_path: str, same_folder: bool, password: str = ""):
        from backend.services.document_security.archive_extraction import extract_archive_any
        from backend.services.document_security.local_operations import unique_path

        source = Path(archive_path).resolve()
        root = source.parent if same_folder else self._choose_output_folder(source.parent)
        if root is None:
            return None
        root.mkdir(parents=True, exist_ok=True)
        base_name = source.name
        for suffix in (".tar.gz", ".tar.bz2", ".tar.xz", ".zip", ".7z", ".rar", ".tgz", ".tbz2", ".txz", ".tar", ".gz", ".bz2", ".xz", ".cab"):
            if base_name.lower().endswith(suffix):
                base_name = base_name[:-len(suffix)]
                break
        destination = unique_path(root, f"{base_name or source.stem}_extracted")
        result = extract_archive_any(source, destination, password or "")
        return {
            "path": str(result.destination),
            "files": result.file_count,
            "bytes": result.total_bytes,
            "type": result.archive_type,
        }

    def secure_all_in_one(
        self,
        source_path: str,
        password: str,
        delete_original: bool,
        reduce_size: bool = False,
    ):
        from backend.services.document_security.local_operations import secure_local_file

        result = secure_local_file(
            Path(source_path),
            password,
            bool(delete_original),
            bool(reduce_size),
        )
        return {
            "path": str(result.output_path),
            "original_trashed": result.original_trashed,
            "note": result.note,
        }


def _start_webview(webview, initializer=None, args: list[object] | None = None) -> None:
    """Use native icon support when available without forcing a package upgrade."""
    # Use a fresh, disposable profile for every launch. Reusing a persistent
    # WebView2 profile reproduced a renderer hang on affected installations,
    # while a failed profile directory must not prevent the app from opening.
    storage_path: Path | None = None
    try:
        profile_root = _local_app_data()
        profile_root.mkdir(parents=True, exist_ok=True)
        storage_path = Path(tempfile.mkdtemp(prefix="WebView2-", dir=profile_root))
    except OSError:
        pass

    kwargs = {"debug": False}
    if storage_path is not None:
        kwargs.update({
            "private_mode": False,
            "storage_path": str(storage_path),
        })
    else:
        kwargs["private_mode"] = True
    icon = _app_icon()
    try:
        if "icon" in inspect.signature(webview.start).parameters and icon.exists():
            kwargs["icon"] = str(icon)
    except (TypeError, ValueError):
        pass

    def launch_initializer(*initializer_args) -> None:
        # Returning immediately is essential: some WebView2 builds postpone
        # the first navigation until the startup callback has completed.
        threading.Thread(
            target=initializer,
            args=initializer_args,
            name="pdf-workbench-engine-launcher",
            daemon=True,
        ).start()

    try:
        if initializer is None:
            webview.start(**kwargs)
        else:
            webview.start(launch_initializer, args=args or [], **kwargs)
    finally:
        if storage_path is not None:
            try:
                import shutil

                shutil.rmtree(storage_path, ignore_errors=True)
            except OSError:
                pass


def _startup_error_html(exc: BaseException) -> str:
    message = html.escape(str(exc) or exc.__class__.__name__)
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#111827;color:#f8fafc;
font-family:'Segoe UI',sans-serif}}main{{max-width:620px;padding:40px;text-align:center}}
h1{{font-size:24px}}p{{color:#fca5a5;line-height:1.55;overflow-wrap:anywhere}}
</style></head><body><main><h1>The local engine could not start</h1><p>{message}</p></main></body></html>"""


def _update_startup_progress(window, percent: int, label: str) -> None:
    script = (
        "window.updateStartupProgress?.("
        f"{int(percent)}, {json.dumps(str(label))}"
        ");"
    )
    try:
        window.evaluate_js(script)
    except Exception:
        # The very first update can race WebView2 script initialization.
        pass


def _emit_startup_progress(progress_pipe, percent: int, label: str) -> None:
    if progress_pipe is None:
        return
    try:
        progress_pipe.send((int(percent), str(label)))
    except (BrokenPipeError, EOFError, OSError):
        pass


def _run_server_process(
    port: int,
    progress_pipe=None,
    warm_start: bool = False,
    parent_pid: int | None = None,
) -> None:
    """Child entry point with a recoverable diagnostic if packaged startup fails."""
    try:
        if parent_pid:
            def stop_with_parent() -> None:
                try:
                    try:
                        import psutil
                    except ImportError:
                        psutil = None

                    while (
                        psutil.pid_exists(parent_pid)
                        if psutil is not None
                        else _process_is_alive(parent_pid)
                    ):
                        time.sleep(0.75)
                finally:
                    os._exit(0)

            threading.Thread(
                target=stop_with_parent,
                name="pdf-workbench-parent-watch",
                daemon=True,
            ).start()
        _run_server_process_impl(port, progress_pipe, warm_start)
    except BaseException:
        try:
            import tempfile
            import traceback

            log_path = Path(tempfile.gettempdir()) / "LocalPDFWorkbench-engine-error.log"
            log_path.write_text(traceback.format_exc(), encoding="utf-8")
        except Exception:
            pass
        raise


def _process_is_alive(pid: int) -> bool:
    """Check a parent PID without making psutil a hard startup dependency."""
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return False
    return True


def _run_server_process_impl(
    port: int,
    progress_pipe=None,
    warm_start: bool = False,
) -> None:
    """Open HTTP first; expensive imports happen after the UI can paint."""
    _emit_startup_progress(progress_pipe, 5, "Starting the isolated local engine…")
    import uvicorn

    try:
        import psutil

        if os.name == "nt":
            psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception:
        pass

    app = _LazyBackendApp(progress_pipe)
    _emit_startup_progress(progress_pipe, 70, "Opening the local API…")
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    _emit_startup_progress(progress_pipe, 98, "Waiting for the application shell…")
    server.run()


def _initialize_backend(
    window,
    gateway_url: str,
    engine_port: int,
    state: dict[str, object],
    closed: threading.Event,
) -> None:
    """Start the isolated engine without making cross-thread WebView calls."""
    try:
        if closed.is_set():
            return
        progress_reader, progress_writer = multiprocessing.Pipe(duplex=False)
        state["progress_reader"] = progress_reader
        process = multiprocessing.Process(
            target=_run_server_process,
            args=(engine_port, progress_writer, _startup_cache_is_warm(), os.getpid()),
            name="pdf-workbench-engine",
            daemon=True,
        )
        state["process"] = process
        process.start()
        progress_writer.close()

        engine_ready = False
        while not closed.is_set():
            while progress_reader.poll():
                try:
                    state["startup_progress"] = progress_reader.recv()
                except EOFError:
                    break
            if not process.is_alive():
                raise RuntimeError(
                    f"Local PDF engine exited during startup (exit code {process.exitcode})."
                )
            try:
                with socket.create_connection(("127.0.0.1", engine_port), timeout=0.12):
                    engine_ready = True
                    break
            except OSError:
                closed.wait(0.06)

        if closed.is_set():
            if process.is_alive():
                process.terminate()
            return
        if not engine_ready:
            return
        gateway = state.get("gateway")
        if not isinstance(gateway, _GatewayServer):
            raise RuntimeError("The local UI gateway is unavailable.")
        gateway.engine_port = engine_port
    except BaseException as exc:
        state["error"] = exc


def _pywebview_main_impl() -> None:
    try:
        import webview
    except ImportError as exc:
        raise RuntimeError(
            "pywebview is not installed. Activate .venv and run: "
            "python -m pip install -r requirements.txt"
        ) from exc

    webview.settings["ALLOW_DOWNLOADS"] = True
    _set_windows_app_identity()

    engine_port = _free_local_port()
    desktop_api = DesktopApi()
    closed = threading.Event()
    server = None
    server_thread: threading.Thread | None = None

    def stop_server() -> None:
        closed.set()
        if server is not None:
            server.should_exit = True
        desktop_api.ready_event.set()

    # Bring up only the tiny lazy ASGI shell before WebView2 starts. Heavy
    # feature imports do not run until the HTML loading screen is already
    # painting, and the browser talks to the engine directly (no Python proxy).
    try:
        # Keep the engine in this process. A frozen PyInstaller executable can
        # open the child socket successfully but fail to dispatch HTTP requests
        # after multiprocessing bootstraps its own copy of the executable.
        # Uvicorn is lightweight here because backend imports remain lazy, and
        # a thread also makes shutdown deterministic when the window closes.
        import uvicorn

        app = _LazyBackendApp()
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=engine_port,
            log_level="warning",
            access_log=False,
        )
        server = uvicorn.Server(config)
        server_thread = threading.Thread(
            target=server.run,
            name="pdf-workbench-engine",
            daemon=True,
        )
        server_thread.start()
        _wait_for_port(engine_port)

        warm_cache = "1" if _startup_cache_is_warm() else "0"
        gateway_url = (
            f"http://127.0.0.1:{engine_port}/"
            f"?startup_cache={warm_cache}&asset_version={STARTUP_CACHE_VERSION}"
        )
        window = webview.create_window(
            APP_TITLE,
            url=gateway_url,
            js_api=desktop_api,
            width=1420,
            height=900,
            min_size=(1050, 680),
            resizable=True,
            text_select=True,
            background_color="#0b1220",
        )
        if window is None:
            raise RuntimeError("The desktop window could not be created.")
        desktop_api.window = window
        window.events.closed += stop_server
        _start_webview(webview)
    finally:
        stop_server()
        if server_thread is not None:
            server_thread.join(timeout=3.0)


def _browser_executable() -> Path:
    """Return a full browser installation, independent of PATH/associations."""
    candidates: list[Path] = []
    for environment_name, suffix in (
        ("PROGRAMFILES", "Google/Chrome/Application/chrome.exe"),
        ("PROGRAMFILES(X86)", "Google/Chrome/Application/chrome.exe"),
        ("LOCALAPPDATA", "Google/Chrome/Application/chrome.exe"),
        ("PROGRAMFILES", "Microsoft/Edge/Application/msedge.exe"),
        ("PROGRAMFILES(X86)", "Microsoft/Edge/Application/msedge.exe"),
        ("LOCALAPPDATA", "Microsoft/Edge/Application/msedge.exe"),
    ):
        root = os.environ.get(environment_name)
        if root:
            candidates.append(Path(root) / Path(suffix))
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise RuntimeError(
        "Google Chrome or Microsoft Edge is required to open Local PDF Workbench."
    )


def _browser_profile_processes(profile: Path) -> list[int]:
    """Find only Chromium processes belonging to this one temporary app profile."""
    try:
        import psutil
    except ImportError:
        return []
    marker = str(profile.resolve()).casefold()
    matches: list[int] = []
    for process in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if (process.info["name"] or "").casefold() not in {
                "chrome.exe",
                "msedge.exe",
            }:
                continue
            command_line = " ".join(process.info["cmdline"] or []).casefold()
            if marker in command_line:
                matches.append(int(process.info["pid"]))
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    return matches


def _wait_for_browser_window(process: subprocess.Popen, profile: Path) -> None:
    """Keep the local engine alive for the lifetime of the Chromium app window."""
    observed = False
    discovery_deadline = time.monotonic() + 20.0
    while True:
        matches = _browser_profile_processes(profile)
        if matches:
            observed = True
        elif observed:
            return
        elif process.poll() is not None and time.monotonic() >= discovery_deadline:
            raise RuntimeError("The desktop browser window closed before it became ready.")
        time.sleep(0.35)


def _browser_main_impl() -> None:
    """Run the UI in Chromium app mode, outside Python/.NET's GUI event loop."""
    engine_port = _free_local_port()
    process = multiprocessing.Process(
        target=_run_server_process,
        args=(engine_port, None, _startup_cache_is_warm(), os.getpid()),
        name="pdf-workbench-engine",
        daemon=True,
    )
    process.start()
    profile = Path(tempfile.mkdtemp(prefix="LocalPDFWorkbench-browser-"))
    try:
        _wait_for_port(engine_port, timeout=None, process=process)
        warm_cache = "1" if _startup_cache_is_warm() else "0"
        url = (
            f"http://127.0.0.1:{engine_port}/"
            f"?startup_cache={warm_cache}&asset_version={STARTUP_CACHE_VERSION}"
        )
        browser = _browser_executable()
        browser_process = subprocess.Popen([
            str(browser),
            f"--app={url}",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-mode",
            "--disable-component-update",
            "--window-size=1420,900",
        ])
        _wait_for_browser_window(browser_process, profile)
    finally:
        if process.is_alive():
            process.terminate()
        process.join(timeout=5.0)
        try:
            import shutil

            shutil.rmtree(profile, ignore_errors=True)
        except OSError:
            pass


def _main_impl() -> None:
    # Prefer a full Chromium app window. Recent Windows Administrator
    # Protection/WebView2 combinations can start the WebView2 renderer under a
    # different security token than the Python host. In that state WebView2
    # cannot write its own EBWebView directory and aborts before our UI loads.
    # The localhost HTTP bridge already provides every native file operation,
    # so the full browser shell loses no application features and avoids the
    # WebView2 data-directory failure entirely.
    try:
        _browser_main_impl()
        return
    except RuntimeError as browser_error:
        # Keep PyWebView as a compatibility fallback for machines where a full
        # Chrome/Edge installation genuinely is unavailable.
        try:
            import webview  # noqa: F401
        except ImportError:
            raise browser_error
        _pywebview_main_impl()


def main() -> None:
    """GUI entry point used by source runs and the venv launcher."""
    multiprocessing.freeze_support()
    try:
        # Processing ordinary user-selected documents does not require an
        # elevated desktop process. Staying at the caller's normal integrity
        # level also ensures the Chromium profile and file dialogs use the same
        # Windows identity as the signed-in user.
        _main_impl()
    except BaseException as exc:
        _fatal_message(str(exc) or exc.__class__.__name__)
        raise


if __name__ == "__main__":
    main()
