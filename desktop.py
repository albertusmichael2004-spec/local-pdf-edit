from __future__ import annotations

import inspect
import multiprocessing
import os
import socket
import sys
import threading
import time

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

import uvicorn

from backend.core.paths import app_icon
from backend.main import app


APP_TITLE = "Local PDF Workbench"
APP_ID = "LocalPDFWorkbench.Desktop"


def _free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_port(port: int, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                return
        except OSError:
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


def _fatal_message(message: str) -> None:
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, APP_TITLE, 0x10)
            return
        except Exception:
            pass
    print(message, file=sys.stderr)


def _start_webview(webview) -> None:
    """Use native icon support when available without forcing a package upgrade."""
    kwargs = {"debug": False}
    try:
        if "icon" in inspect.signature(webview.start).parameters and app_icon().exists():
            kwargs["icon"] = str(app_icon())
    except (TypeError, ValueError):
        pass
    webview.start(**kwargs)


def main() -> None:
    try:
        import webview
    except ImportError as exc:
        raise RuntimeError(
            "pywebview is not installed. Activate .venv and run: "
            "python -m pip install -r requirements.txt"
        ) from exc

    webview.settings["ALLOW_DOWNLOADS"] = True
    _set_windows_app_identity()

    port = _free_local_port()
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None
    thread = threading.Thread(
        target=server.run,
        name="pdf-workbench-server",
        daemon=True,
    )
    thread.start()
    _wait_for_port(port)

    window = webview.create_window(
        APP_TITLE,
        f"http://127.0.0.1:{port}/",
        width=1420,
        height=900,
        min_size=(1050, 680),
        resizable=True,
        text_select=True,
    )
    window.events.closed += lambda: setattr(server, "should_exit", True)
    _start_webview(webview)
    server.should_exit = True
    thread.join(timeout=2.0)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    try:
        main()
    except BaseException as exc:
        _fatal_message(str(exc) or exc.__class__.__name__)
        raise
