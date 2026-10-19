"""Referrer normalisation."""

from urllib.parse import urlsplit


def referrer_host(referrer: str | None) -> str | None:
    """Reduce a Referer header to its host ("news.ycombinator.com"); None for direct traffic.

    Hosts aggregate cleanly for the "top referrers" chart, and dropping the path avoids
    storing tokens or personal data that full referrer URLs sometimes contain.
    """
    if not referrer:
        return None
    host = urlsplit(referrer.strip()).hostname
    if not host:
        return None
    host = host.lower().rstrip(".")
    return host.removeprefix("www.")[:255] or None
