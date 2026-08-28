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


def test_image_ocr_export_pdf_and_docx(
    tmp_path: Path,
    monkeypatch,
):
    import backend.services.convert_to_pdf.jpg_to_text_to_pdf.service as image_ocr_service
    
    from backend.services.shared.ocr.models import (
        OCRPage,
        OCRWord,
    )

    image_a = tmp_path / "page_a.png"
    image_b = tmp_path / "page_b.png"

    for path in (
        image_a,
        image_b,
    ):
        image = Image.new(
            "RGB",
            (240, 120),
            "white",
        )

        image.save(path)
        image.close()

    monkeypatch.setattr(
        image_ocr_service,
        "find_tesseract",
        lambda: "tesseract-test",
    )

    def fake_recognize_images(
        image_paths,
        tesseract_executable,
        language,
        quality,
    ):
        results = []

        for index, path in enumerate(
            image_paths,
            start=1,
        ):
            results.append(
                OCRPage(
                    source_path=path,
                    source_width=240,
                    source_height=120,
                    ocr_width=240,
                    ocr_height=120,
                    words=[
                        OCRWord(
                            text=f"Page {index}",
                            confidence=98.0,
                            left=20,
                            top=20,
                            width=70,
                            height=18,
                            block=1,
                            paragraph=1,
                            line=1,
                        ),
                        OCRWord(
                            text="OCR",
                            confidence=97.0,
                            left=100,
                            top=20,
                            width=40,
                            height=18,
                            block=1,
                            paragraph=1,
                            line=1,
                        ),
                    ],
                    confidence=97.5,
                    psm=3,
                    variant="test",
                )
            )

        return results

    monkeypatch.setattr(
        image_ocr_service,
        "recognize_images",
        fake_recognize_images,
    )

    pdf_output = tmp_path / "ocr_output.pdf"

    pdf_count = (
        image_ocr_service
        .jpg_to_text_to_pdf_or_word(
            image_paths=[
                image_a,
                image_b,
            ],
            output_path=pdf_output,
            output_format="pdf",
            language="eng",
            quality="accurate",
            layout_mode="preserve",
        )
    )

    assert pdf_count == 2
    assert pdf_output.exists()
    assert pdf_output.stat().st_size > 0

    with pdf_output.open("rb") as handle:
        assert handle.read(5) == b"%PDF-"

    docx_output = tmp_path / "ocr_output.docx"

    docx_count = (
        image_ocr_service
        .jpg_to_text_to_pdf_or_word(
            image_paths=[
                image_a,
                image_b,
            ],
            output_path=docx_output,
            output_format="docx",
            language="eng",
            quality="accurate",
            layout_mode="editable",
        )
    )

    assert docx_count == 2
    assert docx_output.exists()
    assert docx_output.stat().st_size > 0