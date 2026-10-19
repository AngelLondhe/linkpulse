"""Cheap bot / crawler / link-preview detection.

A single precompiled regex is fast enough for the redirect path (it is not full UA parsing).
The worker combines it with the `user-agents` parser for the stored device_type.
"""

import re

BOT_PATTERN = re.compile(
    r"bot\b|bot/|crawl|spider|slurp|preview|scanner|monitor|headless|"
    r"facebookexternalhit|facebookcatalog|embedly|whatsapp|telegram|skypeuripreview|"
    r"slack|discord|bitlybot|vkshare|pinterest|redditbot|quora link|outbrain|"
    r"curl/|wget/|python-requests|python-httpx|aiohttp|go-http-client|okhttp|java/|"
    r"libwww|httpclient|axios/|node-fetch|postman",
    re.IGNORECASE,
)


def looks_like_bot(user_agent: str | None) -> bool:
    """True for crawlers, link unfurlers (Slack, WhatsApp, ...) and HTTP libraries.

    A missing User-Agent counts as a bot: every real browser sends one.
    """
    if not user_agent or not user_agent.strip():
        return True
    return BOT_PATTERN.search(user_agent) is not None
