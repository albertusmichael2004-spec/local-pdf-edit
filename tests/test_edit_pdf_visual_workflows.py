from __future__ import annotations

from pathlib import Path

import fitz

from backend.services.edit_pdf.add_watermark import WatermarkRule, add_text_watermarks
from backend.services.edit_pdf.crop_pdf import crop_pages_with_plan
from backend.services.edit_pdf.organize_pdf import organize_with_plan
from backend.services.edit_pdf.rotate_pdf import rotate_pages_with_plan
from backend.services.shared.preview import render_page_preview


def test_organize_plan_supports_blank_rotation_and_reorder(tmp_path: Path, make_pdf):
    source = make_pdf(tmp_path / "source.pdf", pages=3)
    output = tmp_path / "organized.pdf"
    count = organize_with_plan(
        source,
        output,
        [
            {"source_page": 3, "rotation": 90},
            {"source_page": None, "width_pt": 400, "height_pt": 600},
            {"source_page": 1, "rotation": 0},
        ],
    )
    assert count == 3
    with fitz.open(output) as doc:
        assert doc.page_count == 3
        assert doc[0].rotation == 90
        assert doc[1].get_text().strip() == ""
        assert "Page 1" in doc[2].get_text()


def test_preview_exposes_page_dimensions(tmp_path: Path, make_pdf):
    source = make_pdf(tmp_path / "source.pdf", pages=1)
    preview = render_page_preview(source, 1)
    assert preview.page == 1
    assert preview.image.startswith("data:image/jpeg;base64,")
    assert preview.width_pt == 400
    assert preview.height_pt == 600


def test_multiple_watermark_rules_can_target_different_pages(tmp_path: Path, make_pdf):
    source = make_pdf(tmp_path / "source.pdf", pages=3)
    output = tmp_path / "watermarked.pdf"
    add_text_watermarks(
        source,
        output,
        [
            WatermarkRule("ONE", {0}, opacity=0.4, font_size=24, rotation=0, font_key="arial"),
            WatermarkRule("THREE", {2}, opacity=0.4, font_size=24, rotation=0, font_key="times-new-roman"),
        ],
    )
    with fitz.open(output) as doc:
        assert "ONE" in doc[0].get_text()
        assert "ONE" not in doc[1].get_text()
        assert "THREE" in doc[2].get_text()


def test_rotation_plan_supports_different_angles_per_page(tmp_path: Path, make_pdf):
    source = make_pdf(tmp_path / "source.pdf", pages=3)
    output = tmp_path / "rotated-plan.pdf"
    rotate_pages_with_plan(source, output, {0: 90, 1: 180})
    with fitz.open(output) as doc:
        assert [page.rotation for page in doc] == [90, 180, 0]


def test_crop_plan_supports_different_margins_per_page(tmp_path: Path, make_pdf):
    source = make_pdf(tmp_path / "source.pdf", pages=3)
    output = tmp_path / "cropped-plan.pdf"
    crop_pages_with_plan(
        source,
        output,
        {
            0: (10, 0, 0, 0),
            1: (0, 20, 0, 0),
        },
    )
    with fitz.open(output) as doc:
        assert doc[0].rect.width < 400
        assert doc[0].rect.height == 600
        assert doc[1].rect.width == 400
        assert doc[1].rect.height < 600
        assert doc[2].rect.width == 400
        assert doc[2].rect.height == 600
