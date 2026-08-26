from __future__ import annotations

from pathlib import Path

import fitz

from backend.core.errors import CompressionError


def optimize_structure(input_path: Path, output_path: Path) -> None:
    """Losslessly clean and deflate PDF streams using PyMuPDF.

    PyMuPDF has added save options over time. This routine deliberately falls
    back to a conservative argument set so an existing venv with an older
    supported PyMuPDF does not turn compression into a 500/505-style failure.
    """
    try:
        with fitz.open(input_path) as doc:
            if doc.needs_pass:
                raise CompressionError("Encrypted PDFs must be decrypted before compression.")
            preferred = dict(
                garbage=4,
                clean=True,
                deflate=True,
                deflate_images=True,
                deflate_fonts=True,
                use_objstms=1,
                compression_effort=100,
            )
            try:
                doc.save(output_path, **preferred)
            except TypeError:
                # Compatibility with older PyMuPDF releases already present in
                # a user's venv. These options still provide lossless cleanup.
                conservative = dict(
                    garbage=4,
                    clean=True,
                    deflate=True,
                    deflate_images=True,
                    deflate_fonts=True,
                )
                try:
                    doc.save(output_path, **conservative)
                except TypeError:
                    doc.save(output_path, garbage=4, clean=True, deflate=True)
    except CompressionError:
        raise
    except Exception as exc:
        raise CompressionError(f"PDF optimization failed: {exc}") from exc
