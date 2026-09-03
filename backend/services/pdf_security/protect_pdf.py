from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader, PdfWriter

from backend.core.errors import SecurityError
from backend.core.progress import report_fraction, report_progress

def protect_pdf(input_path: Path, output_path: Path, password: str) -> int:
    if not password:
        raise SecurityError("Enter a password to protect the PDF.")
    try:
        reader = PdfReader(str(input_path))
        if reader.is_encrypted:
            raise SecurityError("Input PDF is already encrypted. Unlock it first.")
        writer = PdfWriter()
        try:
            total = len(reader.pages)
            for index, page in enumerate(reader.pages, start=1):
                writer.add_page(page)
                report_fraction("Preparing pages for AES-256 protection", index, total, 24, 78)
            if reader.metadata:
                writer.add_metadata({k: str(v) for k, v in reader.metadata.items() if v is not None})
            report_progress("Encrypting PDF with AES-256", percent=84)
            writer.encrypt(user_password=password, owner_password=password, algorithm="AES-256")
            with output_path.open("wb") as fh:
                writer.write(fh)
            return len(reader.pages)
        finally:
            writer.close()
    except SecurityError:
        raise
    except Exception as exc:
        raise SecurityError(f"Protect PDF failed: {exc}") from exc
