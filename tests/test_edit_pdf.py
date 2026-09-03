from pathlib import Path

import fitz
from pypdf import PdfReader

from backend.services.edit_pdf.add_watermark import add_text_watermark
from backend.services.edit_pdf.compress_pdf import compress_to_target_range
from backend.services.edit_pdf.crop_pdf import crop_pages
from backend.services.edit_pdf.extract_pages import extract_pages
from backend.services.edit_pdf.organize_pdf import organize_pages
from backend.services.edit_pdf.remove_pages import remove_pages
from backend.services.edit_pdf.rotate_pdf import rotate_pages
from backend.services.shared.compression.ghostscript import build_ghostscript_command, profile_from_strength
from backend.services.shared.compression.models import PRESETS


def test_edit_operations(tmp_path: Path, make_pdf):
    source = make_pdf(tmp_path / "source.pdf", 4)

    removed = tmp_path / "removed.pdf"
    assert remove_pages(source, removed, {1}) == 3
    assert len(PdfReader(str(removed)).pages) == 3

    extracted = tmp_path / "extracted.pdf"
    assert extract_pages(source, extracted, [3, 0]) == 2
    assert len(PdfReader(str(extracted)).pages) == 2

    organized = tmp_path / "organized.pdf"
    assert organize_pages(source, organized, [2, 1, 0]) == 3

    rotated = tmp_path / "rotated.pdf"
    rotate_pages(source, rotated, {0}, 90)
    assert PdfReader(str(rotated)).pages[0].get("/Rotate") == 90

    watermarked = tmp_path / "watermark.pdf"
    add_text_watermark(source, watermarked, "CONFIDENTIAL", None, 0.2, 32, 45)
    assert watermarked.stat().st_size > 0

    cropped = tmp_path / "cropped.pdf"
    crop_pages(source, cropped, 5, 5, 5, 5, None)
    with fitz.open(cropped) as doc:
        assert doc[0].rect.width < 400
        assert doc[0].rect.height < 600


def test_custom_compression_returns_original_when_already_in_target(tmp_path: Path, make_pdf):
    source = make_pdf(tmp_path / "source.pdf", 1)
    size = source.stat().st_size
    output = tmp_path / "compressed.pdf"
    result = compress_to_target_range(
        source,
        output,
        max(1, size - 100),
        size + 100,
        timeout_seconds=1,
    )
    assert result.achieved_target is True
    assert output.read_bytes() == source.read_bytes()


def test_recommended_compression_forces_jpeg_reencode(tmp_path: Path):
    command = build_ghostscript_command(
        "gs",
        tmp_path / "source.pdf",
        tmp_path / "output.pdf",
        PRESETS["recommended"],
    )
    assert "-dPassThroughJPEGImages=false" in command
    assert "-dPassThroughJPXImages=false" in command
    parameters = command[command.index("-c") + 1]
    assert "/QFactor 0.550" in parameters
    assert command[-2] == "-f"


def test_custom_strength_changes_real_pdfwrite_image_quality():
    gentle = profile_from_strength(0.0)
    strong = profile_from_strength(1.0)
    assert gentle.force_jpeg_reencode is False
    assert strong.force_jpeg_reencode is True
    assert gentle.jpeg_qfactor < strong.jpeg_qfactor


def test_extreme_preset_keeps_readable_image_resolution():
    profile = PRESETS["extreme"]
    assert profile.dpi >= 150
    assert profile.mono_dpi >= 300
    assert profile.force_jpeg_reencode is True
    assert profile.jpeg_qfactor > PRESETS["recommended"].jpeg_qfactor
