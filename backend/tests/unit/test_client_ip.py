import pytest

from app.utils.client_ip import parse_networks, resolve_client_ip

PROXIES = parse_networks(("10.0.0.0/8", "127.0.0.1"))


def test_without_proxy_config_header_is_ignored() -> None:
    assert resolve_client_ip("203.0.113.9", "1.2.3.4", ()) == "203.0.113.9"


def test_header_from_untrusted_peer_is_ignored() -> None:
    assert resolve_client_ip("198.51.100.7", "1.2.3.4", PROXIES) == "198.51.100.7"


def test_trusted_proxy_uses_forwarded_client() -> None:
    assert resolve_client_ip("10.1.2.3", "203.0.113.9", PROXIES) == "203.0.113.9"


def test_spoofed_leftmost_entries_are_ignored() -> None:
    # Client sent "X-Forwarded-For: 6.6.6.6"; our proxy appended the real address it saw.
    header = "6.6.6.6, 203.0.113.9, 10.0.0.5"
    assert resolve_client_ip("10.1.2.3", header, PROXIES) == "203.0.113.9"


def test_all_hops_trusted_falls_back_to_leftmost() -> None:
    assert resolve_client_ip("10.1.2.3", "10.0.0.7, 10.0.0.5", PROXIES) == "10.0.0.7"


def test_missing_peer() -> None:
    assert resolve_client_ip(None, None, PROXIES) == "unknown"


def test_invalid_network_raises() -> None:
    with pytest.raises(ValueError):
        parse_networks(("not-an-ip",))
