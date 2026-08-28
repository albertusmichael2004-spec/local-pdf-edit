from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile

from PIL import Image

from backend.core.errors import OCRError
from backend.core.subprocesses import run_hidden


def image_to_searchable_pdf(
    image: Image.Image,
    tesseract_executable: str,
    language: str = "eng",
    timeout_seconds: int = 180,
) -> bytes:
    """
    Run Tesseract directly and return a searchable single-page PDF.

    The child process is always hidden on Windows.
    """

    with tempfile.TemporaryDirectory(
        prefix="pdf-workbench-ocr-"
    ) as temp_dir:
        workspace = Path(temp_dir)

        input_image = workspace / "page.png"
        output_base = workspace / "ocr_page"
        output_pdf = workspace / "ocr_page.pdf"

        image.save(
            input_image,
            format="PNG",
        )

        command = [
            tesseract_executable,
            str(input_image),
            str(output_base),
            "-l",
            language,
            "pdf",
        ]

        try:
            result = run_hidden(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise OCRError(
                f"Tesseract OCR exceeded the "
                f"{timeout_seconds}s processing timeout."
            ) from exc
        except OSError as exc:
            raise OCRError(f"Tesseract could not be started: {exc}") from exc

        if result.returncode != 0:
            detail = (
                result.stderr
                or result.stdout
                or "Unknown Tesseract error"
            ).strip()

            raise OCRError(
                f"Tesseract OCR failed: {detail[-1200:]}"
            )

        if not output_pdf.exists():
            raise OCRError(
                "Tesseract completed but did not create a PDF."
            )

        return output_pdf.read_bytes()

def image_to_text(
    image: Image.Image,
    tesseract_executable: str,
    language: str = "eng",
    timeout_seconds: int = 180,
    page_segmentation_mode: int = 3,
) -> str:
    """Run Tesseract directly and return recognized UTF-8 text."""

    with tempfile.TemporaryDirectory(
        prefix="pdf-workbench-ocr-text-"
    ) as temp_dir:
        workspace = Path(temp_dir)
        input_image = workspace / "page.png"

        image.save(
            input_image,
            format="PNG",
        )

        command = [
            tesseract_executable,
            str(input_image),
            "stdout",
            "-l",
            language,
            "--psm",
            str(page_segmentation_mode),
        ]

        try:
            result = run_hidden(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                check=False,
            )

        except subprocess.TimeoutExpired as exc:
            raise OCRError(
                f"Tesseract OCR exceeded the "
                f"{timeout_seconds}s processing timeout."
            ) from exc

        except OSError as exc:
            raise OCRError(
                f"Tesseract could not be started: {exc}"
            ) from exc

        if result.returncode != 0:
            detail = (
                result.stderr
                or result.stdout
                or "Unknown Tesseract error"
            ).strip()

            raise OCRError(
                f"Tesseract OCR failed: {detail[-1200:]}"
            )

        return result.stdout.replace("\f", "").strip()