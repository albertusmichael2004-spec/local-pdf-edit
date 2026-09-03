from __future__ import annotations


class PDFWorkbenchError(RuntimeError):
    """Base exception for expected local PDF processing failures."""


class PDFReadError(PDFWorkbenchError):
    pass


class PDFOperationError(PDFWorkbenchError):
    pass


class EditingError(PDFWorkbenchError):
    pass


class CompressionError(PDFWorkbenchError):
    pass


class ConversionError(PDFWorkbenchError):
    pass


class MediaProcessingError(PDFWorkbenchError):
    pass


class OCRError(PDFWorkbenchError):
    pass


class SecurityError(PDFWorkbenchError):
    pass


class DocumentSecurityError(PDFWorkbenchError):
    pass


class PreviewError(PDFWorkbenchError):
    pass
