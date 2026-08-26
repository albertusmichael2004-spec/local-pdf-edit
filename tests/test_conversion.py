from pathlib import Path
import zipfile

from PIL import Image
from pypdf import PdfReader

from backend.services.convert_from_pdf.pdf_to_excel import pdf_to_xlsx
from backend.services.convert_from_pdf.pdf_to_jpg import pdf_to_jpg_zip
from backend.services.convert_from_pdf.pdf_to_powerpoint import pdf_to_pptx
from backend.services.convert_from_pdf.pdf_to_word import pdf_to_docx
from backend.services.convert_to_pdf.html_to_pdf import html_to_pdf
from backend.services.convert_to_pdf.jpg_to_pdf import jpg_to_pdf


def test_local_conversion_outputs(tmp_path: Path, make_pdf):
    source = make_pdf(tmp_path / "source.pdf", 2)
    image_path = tmp_path / "image.jpg"
    image = Image.new("RGB", (320, 180), "white")
    image.save(image_path)
    image.close()

    image_pdf = tmp_path / "images.pdf"
    assert jpg_to_pdf([image_path], image_pdf) == 1
    assert len(PdfReader(str(image_pdf)).pages) == 1

    docx = tmp_path / "pages.docx"
    pdf_to_docx(source, docx)
    assert docx.stat().st_size > 0

    jpg_zip = tmp_path / "pages.zip"
    assert pdf_to_jpg_zip(source, jpg_zip) == 2
    with zipfile.ZipFile(jpg_zip) as archive:
        assert archive.namelist() == ["page_001.jpg", "page_002.jpg"]

    pptx = tmp_path / "pages.pptx"
    assert pdf_to_pptx(source, pptx) == 2

    xlsx = tmp_path / "pages.xlsx"
    sheets, _ = pdf_to_xlsx(source, xlsx)
    assert sheets == 2


def test_html_to_pdf_fallback_or_weasyprint(tmp_path: Path):
    source = tmp_path / "page.html"
    source.write_text("<html><body><h1>Hello</h1><p>Local</p></body></html>", encoding="utf-8")
    output = tmp_path / "page.pdf"
    engine = html_to_pdf(source, output)
    assert output.read_bytes().startswith(b"%PDF-")
    assert engine
