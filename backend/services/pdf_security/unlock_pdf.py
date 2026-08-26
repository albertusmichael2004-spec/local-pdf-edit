from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader, PdfWriter

from backend.core.errors import SecurityError

def unlock_pdf(input_path: Path, output_path: Path, password: str) -> int:
    try:
        reader = PdfReader(str(input_path))
        if reader.is_encrypted:
            status = reader.decrypt(password or "")
            if not status:
                raise SecurityError("Incorrect PDF password.")
        writer = PdfWriter()
        try:
            for page in reader.pages:
                writer.add_page(page)
            if reader.metadata:
                writer.add_metadata({k: str(v) for k, v in reader.metadata.items() if v is not None})
            with output_path.open("wb") as fh:
                writer.write(fh)
            return len(reader.pages)
        finally:
            writer.close()
    except SecurityError:
        raise
    except Exception as exc:
        raise SecurityError(f"Unlock PDF failed: {exc}") from exc
