from pathlib import Path

from pypdf import PdfReader

from backend.services.pdf_security.compare_pdf import compare_pdfs_detailed
from backend.services.pdf_security.compare_sha256 import compare_sha256
from backend.services.pdf_security.protect_pdf import protect_pdf
from backend.services.pdf_security.sha256_pdf import sha256_file
from backend.services.pdf_security.unlock_pdf import unlock_pdf


def test_security_hash_and_password(tmp_path: Path, make_pdf):
    source = make_pdf(tmp_path / "source.pdf", 2)
    protected = tmp_path / "protected.pdf"
    protect_pdf(source, protected, "secret")
    reader = PdfReader(str(protected))
    assert reader.is_encrypted
    assert reader.decrypt("secret")

    unlocked = tmp_path / "unlocked.pdf"
    assert unlock_pdf(protected, unlocked, "secret") == 2
    assert len(sha256_file(source)) == 64
    left, right, identical = compare_sha256(source, source)
    assert identical and left == right


def test_detailed_compare_detects_word_and_character_changes(tmp_path: Path, make_pdf):
    left = make_pdf(tmp_path / "left.pdf", 1, "alpha beta")
    right = make_pdf(tmp_path / "right.pdf", 1, "alpha gamma beta")
    summary, _ = compare_pdfs_detailed(left, right)
    assert summary["different_pages"] == 1
    page = summary["page_results"][0]
    assert page["character_exact"] is False
    assert page["word_sequence_exact"] is False
