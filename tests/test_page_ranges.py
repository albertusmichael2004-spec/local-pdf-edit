import pytest

from backend.utils.page_ranges import parse_group_expression


def test_parse_split_groups():
    groups = parse_group_expression("1-3;4,6,8-10", total_pages=10)
    assert groups[0].pages_zero_based == (0, 1, 2)
    assert groups[1].pages_zero_based == (3, 5, 7, 8, 9)


def test_out_of_bounds_range_rejected():
    with pytest.raises(ValueError):
        parse_group_expression("1-11", total_pages=10)
