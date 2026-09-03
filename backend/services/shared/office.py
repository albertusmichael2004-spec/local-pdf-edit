from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

from backend.core.errors import ConversionError
from backend.core.executables import find_libreoffice
from backend.core.progress import report_progress
from backend.core.subprocesses import run_hidden


def office_to_pdf(input_path: Path, output_path: Path, timeout_seconds: int = 180) -> str:
    """Use local LibreOffice when available and return the engine name."""
    executable = find_libreoffice()
    if not executable:
        raise ConversionError("LibreOffice was not found.")
    output_dir = output_path.parent
    command = [
        executable,
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        str(output_dir),
        str(input_path),
    ]
    try:
        report_progress("LibreOffice is converting the document", percent=38, detail=input_path.name)
        result = run_hidden(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ConversionError("LibreOffice conversion timed out.") from exc
    except OSError as exc:
        raise ConversionError(f"LibreOffice could not be started: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip() or "unknown error"
        raise ConversionError(f"LibreOffice conversion failed: {detail}")

    generated = output_dir / f"{input_path.stem}.pdf"
    if not generated.exists():
        candidates = sorted(
            output_dir.glob("*.pdf"), key=lambda path: path.stat().st_mtime, reverse=True
        )
        if not candidates:
            raise ConversionError("LibreOffice did not produce a PDF.")
        generated = candidates[0]
    if generated.resolve() != output_path.resolve():
        shutil.move(str(generated), str(output_path))
    report_progress("Finalizing converted PDF", percent=94)
    return "LibreOffice"
