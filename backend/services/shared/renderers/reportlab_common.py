from __future__ import annotations

from backend.core.errors import ConversionError

def reportlab_imports():
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.utils import ImageReader
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image as RLImage,
        )
        from reportlab.pdfgen import canvas
        return {
            "colors": colors, "A4": A4, "landscape": landscape,
            "getSampleStyleSheet": getSampleStyleSheet, "ParagraphStyle": ParagraphStyle,
            "TA_LEFT": TA_LEFT, "ImageReader": ImageReader,
            "SimpleDocTemplate": SimpleDocTemplate, "Paragraph": Paragraph, "Spacer": Spacer,
            "Table": Table, "TableStyle": TableStyle, "PageBreak": PageBreak, "RLImage": RLImage,
            "canvas": canvas,
        }
    except ImportError as exc:
        raise ConversionError("ReportLab is required for the built-in Office/HTML fallback. Run pip install -r requirements.txt.") from exc

def safe_para_text(value: object) -> str:
    import html as html_mod
    text = str(value or "").replace("\x00", "").strip()
    return html_mod.escape(text).replace("\n", "<br/>")
