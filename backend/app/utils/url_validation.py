"""Validation of destination URLs for short links."""

import re
from urllib.parse import urlsplit

MAX_URL_LENGTH = 2048
ALLOWED_SCHEMES = frozenset({"http", "https"})
# RFC 1123 labels (letters, digits, hyphen) or an IPv4 literal; IDNs must arrive punycode-encoded
# or as Unicode letters, which the browser will encode.
_HOST_LABEL = re.compile(r"^(?!-)[\w-]{1,63}(?<!-)$", re.UNICODE)
_CONTROL_OR_SPACE = re.compile(r"[\x00-\x20\x7f]")


class InvalidURLError(ValueError):
    """Raised with a human-readable reason when a URL is not acceptable as a redirect target."""


def _normalise_host(host: str) -> str:
    return host.lower().rstrip(".")


def validate_target_url(url: str, own_hosts: frozenset[str]) -> str:
    """Return the trimmed URL if it is a safe redirect target, else raise InvalidURLError.

    Rules: http/https only (blocks javascript:, data:, file:, ...), a valid host, no embedded
    credentials (a common phishing trick: https://bank.com@evil.test), no whitespace or control
    characters, and not pointing at this service itself (would create redirect loops).
    """
    candidate = url.strip()
    if not candidate:
        raise InvalidURLError("URL must not be empty")
    if len(candidate) > MAX_URL_LENGTH:
        raise InvalidURLError(f"URL must be at most {MAX_URL_LENGTH} characters")
    if _CONTROL_OR_SPACE.search(candidate):
        raise InvalidURLError("URL must not contain whitespace or control characters")

    parts = urlsplit(candidate)
    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        raise InvalidURLError("Only http and https URLs are allowed")
    if parts.username is not None or parts.password is not None:
        raise InvalidURLError("URLs with embedded credentials are not allowed")

    host = parts.hostname
    if not host:
        raise InvalidURLError("URL must include a host")
    try:
        _ = parts.port  # raises ValueError for non-numeric / out-of-range ports
    except ValueError as exc:
        raise InvalidURLError("URL has an invalid port") from exc

    host = _normalise_host(host)
    is_ipv6_literal = ":" in host
    if not is_ipv6_literal and not all(_HOST_LABEL.match(label) for label in host.split(".")):
        raise InvalidURLError("URL has an invalid host")
    if host in own_hosts:
        raise InvalidURLError("URL must not point to this link shortener")

    return candidate


def own_hosts_from_urls(*urls: str) -> frozenset[str]:
    """Hosts that belong to this service (used to reject self-referencing links)."""
    hosts = {urlsplit(u).hostname for u in urls}
    return frozenset(_normalise_host(h) for h in hosts if h)
