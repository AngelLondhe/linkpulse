"""User-Agent parsing for click analytics."""

from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from user_agents import parse

from app.utils.bots import looks_like_bot

DeviceType = Literal["mobile", "tablet", "desktop", "bot", "other"]
UNKNOWN = "Unknown"


@dataclass(frozen=True)
class ParsedUserAgent:
    browser: str
    os: str
    device_type: DeviceType


def _family(value: str | None) -> str:
    return UNKNOWN if not value or value == "Other" else value


# Real traffic is dominated by a few thousand distinct UA strings, so caching pays off.
@lru_cache(maxsize=4096)
def parse_user_agent(user_agent: str | None) -> ParsedUserAgent:
    """Classify a User-Agent into browser family, OS family and device type.

    Bots are anything the parser flags, plus link unfurlers / HTTP libraries / missing UAs
    caught by ``looks_like_bot`` (the same rule the redirect path uses for max_clicks).
    """
    if not user_agent:
        return ParsedUserAgent(browser=UNKNOWN, os=UNKNOWN, device_type="bot")

    ua = parse(user_agent)
    device: DeviceType
    if ua.is_bot or looks_like_bot(user_agent):
        device = "bot"
    elif ua.is_tablet:
        device = "tablet"
    elif ua.is_mobile:
        device = "mobile"
    elif ua.is_pc:
        device = "desktop"
    else:
        device = "other"
    return ParsedUserAgent(
        browser=_family(ua.browser.family)[:64], os=_family(ua.os.family)[:64], device_type=device
    )
