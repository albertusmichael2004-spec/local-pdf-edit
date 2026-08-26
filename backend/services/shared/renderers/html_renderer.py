from __future__ import annotations

from pathlib import Path

from backend.core.errors import ConversionError
from backend.services.shared.renderers.reportlab_common import reportlab_imports, safe_para_text

def render_html_to_pdf(input_path: Path, output_path: Path) -> str:
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise ConversionError("beautifulsoup4 is required for the HTML fallback. Run pip install -r requirements.txt.") from exc
    rl = reportlab_imports()
    try:
        raw = input_path.read_text(encoding="utf-8", errors="replace")
        soup = BeautifulSoup(raw, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        styles = rl["getSampleStyleSheet"]()
        story = []
        title = soup.title.string.strip() if soup.title and soup.title.string else input_path.stem
        story.append(rl["Paragraph"](safe_para_text(title), styles["Title"]))
        story.append(rl["Spacer"](1, 10))
        # Extract meaningful block content without making network requests.
        for node in soup.find_all(["h1","h2","h3","h4","p","li","pre","blockquote","table"]):
            if node.name == "table":
                rows = []
                for tr in node.find_all("tr"):
                    row = [safe_para_text(cell.get_text(" ", strip=True)) for cell in tr.find_all(["th","td"])]
                    if row: rows.append(row)
                if rows:
                    table = rl["Table"](rows, repeatRows=1, hAlign="LEFT")
                    table.setStyle(rl["TableStyle"]([("GRID",(0,0),(-1,-1),0.3,rl["colors"].grey),("FONTSIZE",(0,0),(-1,-1),8),("VALIGN",(0,0),(-1,-1),"TOP")]))
                    story.extend([table, rl["Spacer"](1, 8)])
                continue
            text = safe_para_text(node.get_text(" ", strip=True))
            if not text: continue
            style = styles["BodyText"]
            if node.name.startswith("h") and node.name[1:].isdigit():
                style = styles.get(f"Heading{min(6,int(node.name[1:]))}", styles["Heading2"])
            elif node.name == "pre":
                style = styles["Code"]
            story.extend([rl["Paragraph"](text, style), rl["Spacer"](1, 5)])
        if len(story) <= 2:
            text = safe_para_text(soup.get_text("\n", strip=True))
            story.append(rl["Paragraph"](text or "(Empty HTML)", styles["BodyText"]))
        pdf = rl["SimpleDocTemplate"](str(output_path), pagesize=rl["A4"], rightMargin=42, leftMargin=42, topMargin=42, bottomMargin=42)
        pdf.build(story)
        return "Built-in HTML renderer"
    except Exception as exc:
        raise ConversionError(f"Built-in HTML conversion failed: {exc}") from exc
