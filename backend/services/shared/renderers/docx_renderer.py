from __future__ import annotations

from io import BytesIO
from pathlib import Path

from backend.core.errors import ConversionError
from backend.services.shared.renderers.reportlab_common import reportlab_imports, safe_para_text

def render_docx_to_pdf(input_path: Path, output_path: Path) -> str:
    if input_path.suffix.lower() != ".docx":
        raise ConversionError("Legacy .doc files require LibreOffice. Save the file as .docx or install LibreOffice.")
    try:
        from docx import Document
        from docx.table import Table as DocxTable
        from docx.text.paragraph import Paragraph as DocxParagraph
    except ImportError as exc:
        raise ConversionError("python-docx is not installed. Run pip install -r requirements.txt.") from exc
    rl = reportlab_imports()
    try:
        docx = Document(str(input_path))
        styles = rl["getSampleStyleSheet"]()
        body = []
        # Preserve document order for paragraphs and tables.
        for child in docx.element.body.iterchildren():
            if child.tag.endswith('}p'):
                para = DocxParagraph(child, docx)
                text = safe_para_text(para.text)
                if not text:
                    body.append(rl["Spacer"](1, 6))
                    continue
                style = styles["BodyText"]
                try:
                    name = (para.style.name or "").lower()
                    if name.startswith("heading"):
                        level = int(''.join(ch for ch in name if ch.isdigit()) or '1')
                        style = styles.get(f"Heading{min(6, max(1, level))}", styles["Heading1"])
                except Exception:
                    pass
                body.append(rl["Paragraph"](text, style))
                body.append(rl["Spacer"](1, 5))
            elif child.tag.endswith('}tbl'):
                table = DocxTable(child, docx)
                data = [[safe_para_text(cell.text) for cell in row.cells] for row in table.rows]
                if data:
                    t = rl["Table"](data, repeatRows=1, hAlign="LEFT")
                    t.setStyle(rl["TableStyle"]([
                        ("GRID", (0,0), (-1,-1), 0.35, rl["colors"].grey),
                        ("VALIGN", (0,0), (-1,-1), "TOP"),
                        ("FONTSIZE", (0,0), (-1,-1), 8),
                        ("BACKGROUND", (0,0), (-1,0), rl["colors"].whitesmoke),
                    ]))
                    body.extend([t, rl["Spacer"](1, 8)])
        pdf = rl["SimpleDocTemplate"](str(output_path), pagesize=rl["A4"], rightMargin=42, leftMargin=42, topMargin=42, bottomMargin=42)
        pdf.build(body or [rl["Paragraph"]("(Empty document)", styles["BodyText"])])
        return "Built-in DOCX renderer"
    except ConversionError:
        raise
    except Exception as exc:
        raise ConversionError(f"Built-in DOCX conversion failed: {exc}") from exc
