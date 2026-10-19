from app.utils.shortcode import BASE62_ALPHABET, CODE_LENGTH, generate_short_code


def test_alphabet_is_base62() -> None:
    assert len(BASE62_ALPHABET) == 62
    assert len(set(BASE62_ALPHABET)) == 62


def test_codes_have_expected_length_and_charset() -> None:
    for _ in range(500):
        code = generate_short_code()
        assert len(code) == CODE_LENGTH
        assert set(code) <= set(BASE62_ALPHABET)


def test_codes_are_not_repeated_in_practice() -> None:
    codes = {generate_short_code() for _ in range(5000)}
    assert len(codes) == 5000


def test_custom_length() -> None:
    assert len(generate_short_code(12)) == 12
