import pytest

from app.utils.referrer import referrer_host


@pytest.mark.parametrize(
    ("referrer", "expected"),
    [
        (None, None),
        ("", None),
        ("not a url", None),
        ("https://www.Google.com/search?q=secret-token", "google.com"),
        ("https://news.ycombinator.com/item?id=1", "news.ycombinator.com"),
        ("android-app://com.slack/", "com.slack"),
        ("http://t.co./abc", "t.co"),
    ],
)
def test_referrer_is_reduced_to_host(referrer: str | None, expected: str | None) -> None:
    assert referrer_host(referrer) == expected
