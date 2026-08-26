from __future__ import annotations

import sys

from backend.core.subprocesses import run_hidden


def test_run_hidden_executes_child_process_without_recursing():
    result = run_hidden(
        [sys.executable, "-c", "print('ok')"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "ok"
