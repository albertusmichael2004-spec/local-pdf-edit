from scripts.ocr_training_evaluate import (
    character_error_rate,
    duplicate_line_ratio,
    suspicious_token_ratio,
    word_error_rate,
)


def test_character_error_rate_perfect():
    assert (
        character_error_rate(
            "hello",
            "hello",
        )
        == 0
    )


def test_character_error_rate_detects_error():
    assert (
        character_error_rate(
            "hello",
            "hallo",
        )
        > 0
    )


def test_word_error_rate_perfect():
    assert (
        word_error_rate(
            "hello world",
            "hello world",
        )
        == 0
    )


def test_word_error_rate_detects_error():
    assert (
        word_error_rate(
            "hello world",
            "hello there",
        )
        > 0
    )


def test_duplicate_line_ratio():
    text = (
        "First line\n"
        "Second line\n"
        "First line"
    )

    assert (
        duplicate_line_ratio(
            text
        )
        > 0
    )


def test_duplicate_line_ratio_clean():
    assert (
        duplicate_line_ratio(
            "One\nTwo\nThree"
        )
        == 0
    )


def test_suspicious_token_ratio_clean_text():
    assert (
        suspicious_token_ratio(
            "Invoice number 12345"
        )
        == 0
    )



def test_normalize_text_empty_remains_empty():
    from scripts.ocr_training_evaluate import normalize_text

    assert (
        normalize_text(
            "   \n\t  ",
            ignore_case=False,
        )
        == ""
    )
