import pytest

from app.utils.aliases import InvalidAliasError, validate_alias


@pytest.mark.parametrize("alias", ["abc", "my-launch_2026", "A" * 30, "Docs-v2", "x_y"])
def test_valid_aliases(alias: str) -> None:
    assert validate_alias(alias) == alias


@pytest.mark.parametrize(
    ("alias", "reason"),
    [
        ("ab", "3-30 characters"),
        ("a" * 31, "3-30 characters"),
        ("has space", "3-30 characters"),
        ("dot.dot", "3-30 characters"),
        ("slash/path", "3-30 characters"),
        ("émoji", "3-30 characters"),
        ("api", "reserved"),
        ("LOGIN", "reserved"),
        ("Admin", "reserved"),
    ],
)
def test_invalid_aliases(alias: str, reason: str) -> None:
    with pytest.raises(InvalidAliasError, match=reason):
        validate_alias(alias)
