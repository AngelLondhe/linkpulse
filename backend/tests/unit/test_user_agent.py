import pytest

from app.utils.user_agent import parse_user_agent

CHROME_WINDOWS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)
SAFARI_IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
)
SAFARI_IPAD = (
    "Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
)
CHROME_ANDROID = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36"
)
FIREFOX_MAC = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:131.0) Gecko/20100101 Firefox/131.0"
GOOGLEBOT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"


@pytest.mark.parametrize(
    ("ua", "browser", "os", "device"),
    [
        (CHROME_WINDOWS, "Chrome", "Windows", "desktop"),
        (SAFARI_IPHONE, "Mobile Safari", "iOS", "mobile"),
        (SAFARI_IPAD, "Mobile Safari", "iOS", "tablet"),
        (CHROME_ANDROID, "Chrome Mobile", "Android", "mobile"),
        (FIREFOX_MAC, "Firefox", "Mac OS X", "desktop"),
        (GOOGLEBOT, "Googlebot", "Unknown", "bot"),
    ],
)
def test_parses_common_user_agents(ua: str, browser: str, os: str, device: str) -> None:
    parsed = parse_user_agent(ua)

    assert (parsed.browser, parsed.os, parsed.device_type) == (browser, os, device)


def test_unrecognised_user_agent_is_unknown() -> None:
    parsed = parse_user_agent("totally-not-a-browser/0.0")

    assert (parsed.browser, parsed.os, parsed.device_type) == ("Unknown", "Unknown", "other")


@pytest.mark.parametrize(
    "ua",
    [
        None,
        "",
        "Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)",
        "WhatsApp/2.23.20.0",
        "curl/8.4.0",
    ],
)
def test_missing_ua_previews_and_tools_are_bots(ua: str | None) -> None:
    assert parse_user_agent(ua).device_type == "bot"
