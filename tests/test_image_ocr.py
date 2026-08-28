from pathlib import Path
from subprocess import CompletedProcess

import cv2
import numpy as np

from backend.services.convert_to_pdf.jpg_to_text_to_pdf.text_layout import page_lines
from backend.services.shared.ocr.languages import resolve_ocr_language
from backend.services.shared.ocr.models import OCRPage, OCRWord
from backend.services.shared.ocr.preprocess import prepare_ocr_variants
from backend.services.shared.ocr.scoring import candidate_score
from backend.services.shared.ocr.candidate_selection import select_best_candidate
from backend.services.shared.ocr.tesseract_tsv import run_tsv


def word(text: str, confidence: float, left: int, top: int, block: int = 1) -> OCRWord:
    return OCRWord(text, confidence, left, top, 80, 30, block, 1, 1)


def page(words: list[OCRWord], confidence: float = 90) -> OCRPage:
    return OCRPage(Path("page.jpg"), 1000, 1400, 1000, 1400, words, confidence, 3, "test")


def test_preprocess_rectifies_phone_photo(tmp_path: Path):
    image = np.full((1800, 1400, 3), (45, 35, 80), dtype=np.uint8)
    quad = np.array([[180, 100], [1280, 170], [1200, 1700], [110, 1620]], dtype=np.int32)
    cv2.fillConvexPoly(image, quad, (235, 238, 240))
    for row in range(260, 1500, 90):
        cv2.line(image, (280, row), (1080, row + 30), (30, 30, 30), 12)
    source = tmp_path / "phone.jpg"
    cv2.imwrite(str(source), image)
    prepared = prepare_ocr_variants(source, tmp_path / "work")
    assert prepared.source_size == (1400, 1800)
    assert prepared.ocr_size[0] < prepared.ocr_size[1]
    assert len(prepared.variants) == 3
    assert all(path.stat().st_size > 0 for _, path in prepared.variants)
    assert not np.allclose(np.asarray(prepared.inverse_transform), np.eye(3))


def test_candidate_score_penalizes_fragmented_noise():
    clean = page([word("Saudara", 95, 100, 100), word("Fransiskus", 94, 220, 100)])
    noisy_words = [word("|", 97, 10 + index * 20, 100, index) for index in range(12)]
    noisy = page(noisy_words, confidence=97)
    assert candidate_score(clean) > candidate_score(noisy)


def test_visual_line_grouping_merges_labels_and_drops_noise():
    words = [
        word("Saudara-saudari,", 96, 220, 100, 2),
        word("P:", 80, 40, 112, 1),
        word("Santo", 95, 500, 102, 2),
        word("5", 3, 20, 20, 3),
        word("Semanan", 0, 700, 20, 4),
    ]
    assert page_lines(page(words)) == ["P: Saudara-saudari, Santo"]


def test_low_confidence_speaker_label_is_kept():
    words = [word("U:", 0, 40, 100, 1), word("Amin", 95, 220, 100, 2)]
    assert page_lines(page(words)) == ["U: Amin"]


def test_visual_grouping_merges_words_from_different_ocr_blocks():
    words = [word("Kemudian", 95, 100, 100, 1), word("Fransiskus", 95, 300, 102, 8)]
    assert page_lines(page(words)) == ["Kemudian Fransiskus"]


def test_tight_visual_fragments_are_rejoined():
    words = [
        OCRWord("m", 95, 100, 100, 20, 30, 1, 1, 1),
        OCRWord("enyuruh", 95, 123, 100, 100, 30, 2, 1, 1),
    ]
    assert page_lines(page(words)) == ["menyuruh"]


def test_auto_language_prefers_packaged_indonesian(tmp_path: Path):
    (tmp_path / "ind.traineddata").write_bytes(b"model")
    assert resolve_ocr_language("auto", tmp_path) == ("ind", tmp_path)
    assert resolve_ocr_language("eng", tmp_path) == ("eng", None)


def test_tsv_runner_does_not_depend_on_system_config(monkeypatch, tmp_path: Path):
    output = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
    output += '5\t1\t1\t1\t1\t1\t10\t20\t30\t12\t96\t"Bapa\n'
    output += '5\t1\t1\t1\t1\t2\t42\t20\t40\t12\t96\tdunia"\n'
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return CompletedProcess(command, 0, output, "")

    monkeypatch.setattr("backend.services.shared.ocr.tesseract_tsv.run_hidden", fake_run)
    words, confidence = run_tsv(tmp_path / "page.png", "tesseract", "ind", 3, tmp_path)
    assert [word.text for word in words] == ['"Bapa', 'dunia"']
    assert confidence == 96
    assert "tessedit_create_tsv=1" in captured["command"]
    assert "tsv" not in captured["command"]



def test_searchable_pdf_accepts_webp_source(
    tmp_path: Path,
):
    from PIL import Image

    from backend.services.shared.ocr.searchable_pdf import (
        render_searchable_pdf,
    )

    source = (
        tmp_path
        / "page.webp"
    )

    Image.new(
        "RGB",
        (320, 180),
        "white",
    ).save(
        source,
        format="WEBP",
    )

    result = OCRPage(
        source_path=source,
        source_width=320,
        source_height=180,
        ocr_width=320,
        ocr_height=180,
        words=[
            OCRWord(
                "Hello",
                95.0,
                20,
                20,
                70,
                20,
                1,
                1,
                1,
            )
        ],
        confidence=95.0,
        psm=3,
        variant="test",
    )

    output = (
        tmp_path
        / "webp-searchable.pdf"
    )

    render_searchable_pdf(
        [result],
        output,
    )

    assert output.read_bytes().startswith(
        b"%PDF-"
    )



def test_candidate_selection_prefers_complete_page_over_fragmented_noise():
    clean = page(
        [
            word(
                "General",
                94,
                100,
                100,
            ),
            word(
                "document",
                94,
                220,
                100,
            ),
        ]
    )

    noisy = page(
        [
            word(
                "x",
                99,
                10 + index * 30,
                100,
                index + 1,
            )
            for index in range(10)
        ],
        confidence=99,
    )

    assert (
        select_best_candidate(
            [
                noisy,
                clean,
            ]
        )
        is clean
    )
