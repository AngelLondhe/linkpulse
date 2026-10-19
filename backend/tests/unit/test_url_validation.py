import pytest

from app.utils.url_validation import InvalidURLError, own_hosts_from_urls, validate_target_url

OWN = own_hosts_from_urls("https://lnk.example/", "http://localhost:8000")


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com",
        "http://example.com/path?q=1#frag",
        "https://sub.domain.example.co.uk:8443/a/b",
        "HTTPS://Example.COM/MixedCase",
        "http://192.168.1.10/",
        "http://[2001:db8::1]/",
        "https://bücher.example/",
        "  https://example.com/trimmed  ",
    ],
)
def test_accepts_valid_urls(url: str) -> None:
    assert validate_target_url(url, OWN) == url.strip()


@pytest.mark.parametrize(
    ("url", "reason"),
    [
        ("javascript:alert(1)", "Only http and https"),
        ("JaVaScRiPt:alert(1)", "Only http and https"),
        ("data:text/html,<script>alert(1)</script>", "Only http and https"),
        ("file:///etc/passwd", "Only http and https"),
        ("ftp://example.com", "Only http and https"),
        ("example.com", "Only http and https"),
        ("//example.com", "Only http and https"),
        ("https://", "must include a host"),
        ("https://user:pass@example.com", "embedded credentials"),
        ("https://bank.example@evil.example", "embedded credentials"),
        ("https://exa mple.com", "whitespace"),
        ("https://example.com/\nX-Injected: 1", "whitespace"),
        ("https://example.com:99999", "invalid port"),
        ("https://-bad-.example", "invalid host"),
        ("https://exa_mple..com", "invalid host"),
        ("https://lnk.example/abc1234", "this link shortener"),
        ("https://LNK.EXAMPLE./abc", "this link shortener"),
        ("http://localhost:8000/xyz", "this link shortener"),
        ("", "must not be empty"),
        ("https://example.com/" + "a" * 2048, "at most"),
    ],
)
def test_rejects_invalid_urls(url: str, reason: str) -> None:
    with pytest.raises(InvalidURLError, match=reason):
        validate_target_url(url, OWN)


def test_own_hosts_are_normalised() -> None:
    assert own_hosts_from_urls("https://Lnk.Example./", "not a url") == frozenset({"lnk.example"})
