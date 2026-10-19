import pytest

from app.utils.bots import looks_like_bot
from tests.unit.test_user_agent import CHROME_ANDROID, CHROME_WINDOWS, FIREFOX_MAC, SAFARI_IPHONE


@pytest.mark.parametrize(
    "ua",
    [
        "Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)",
        "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
        "WhatsApp/2.23.20.0",
        "TelegramBot (like TwitterBot)",
        "Mozilla/5.0 (compatible; Discordbot/2.0; +https://discordapp.com)",
        "Twitterbot/1.0",
        "LinkedInBot/1.0 (compatible; Mozilla/5.0; Apache-HttpClient +http://www.linkedin.com)",
        "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
        "curl/8.4.0",
        "python-requests/2.32.3",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "HeadlessChrome/120.0",
        "",
        None,
    ],
)
def test_detects_bots_and_previews(ua: str | None) -> None:
    assert looks_like_bot(ua)


@pytest.mark.parametrize("ua", [CHROME_WINDOWS, SAFARI_IPHONE, CHROME_ANDROID, FIREFOX_MAC])
def test_real_browsers_are_not_bots(ua: str) -> None:
    assert not looks_like_bot(ua)
