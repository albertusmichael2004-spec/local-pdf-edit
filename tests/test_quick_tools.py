from pathlib import Path
import zipfile

from backend.services.quick_tools.merge_pdf import merge_pdfs
from backend.services.quick_tools.split_pdf import groups_by_approx_size, split_pdf_to_zip
from backend.services.shared.pdf_reader import get_pdf_page_count
from backend.utils.page_ranges import groups_every_n_pages, parse_group_expression


def test_merge_and_split(tmp_path: Path, make_pdf):
    first = make_pdf(tmp_path / "a.pdf", 2, "A")
    second = make_pdf(tmp_path / "b.pdf", 3, "B")
    merged = tmp_path / "merged.pdf"
    assert merge_pdfs([first, second], merged) == 5
    assert get_pdf_page_count(merged) == 5

    groups = parse_group_expression("1-2;3-5", 5)
    output_zip = tmp_path / "split.zip"
    assert split_pdf_to_zip(merged, groups, output_zip, "merged") == 2
    with zipfile.ZipFile(output_zip) as archive:
        assert len(archive.namelist()) == 2


def test_size_split_and_page_groups(tmp_path: Path, make_pdf):
    source = make_pdf(tmp_path / "source.pdf", 4)
    groups, oversized = groups_by_approx_size(source, 60 * 1024)
    assert groups
    assert oversized == []
    assert [group.pages_zero_based for group in groups_every_n_pages(12, 5)] == [
        (0, 1, 2, 3, 4),
        (5, 6, 7, 8, 9),
        (10, 11),
    ]
