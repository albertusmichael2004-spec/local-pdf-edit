from __future__ import annotations

import os
import subprocess
from typing import Any, Sequence


def hidden_process_kwargs() -> dict[str, Any]:
    """
    Return subprocess options that prevent child console windows
    from appearing on Windows.

    On Linux/macOS this returns an empty dictionary.
    """
    if os.name != "nt":
        return {}

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE

    return {
        "startupinfo": startupinfo,
        "creationflags": subprocess.CREATE_NO_WINDOW,
    }


def run_hidden(
    command: Sequence[str],
    **kwargs: Any,
) -> subprocess.CompletedProcess:
    """
    Run an external executable without displaying a console window.
    """
    process_kwargs = hidden_process_kwargs()

    # Allow caller-specific options such as timeout, stdout, stderr, etc.
    process_kwargs.update(kwargs)

    return subprocess.run(
        command,
        **process_kwargs,
    )