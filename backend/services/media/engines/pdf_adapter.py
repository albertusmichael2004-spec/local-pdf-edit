from __future__ import annotations

from pathlib import Path

from backend.core.errors import MediaProcessingError
from backend.services.convert_from_pdf.pdf_to_excel import pdf_to_xlsx
from backend.services.convert_from_pdf.pdf_to_powerpoint import pdf_to_pptx
from backend.services.convert_from_pdf.pdf_to_word import pdf_to_docx
from .base import MediaEngine
from .ebook import EbookEngine
from ..models import JobOptions, MediaProbeResult


class PDFEngineAdapter(MediaEngine):
    """Reuse the established PDF converters instead of introducing a second engine."""

    def process(self, source: Path, output: Path, probe: MediaProbeResult, options: JobOptions) -> tuple[str, ...]:
        if options.target_format == "docx":
            pdf_to_docx(source, output)
        elif options.target_format == "pptx":
            pdf_to_pptx(source, output)
        elif options.target_format == "xlsx":
            pdf_to_xlsx(source, output)
        elif options.target_format == "epub":
            return EbookEngine().process(source, output, probe, options)
        else:
            raise MediaProcessingError(f"Unsupported PDF target: {options.target_format}.")
        if not output.exists() or not output.stat().st_size:
            raise MediaProcessingError(f"PDF conversion created no usable output for {source.name}.")
        return ()
