"""Resolve the real client IP, honouring X-Forwarded-For only from trusted proxies."""

import ipaddress
from collections.abc import Iterable
from functools import lru_cache

IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


@lru_cache(maxsize=8)
def parse_networks(entries: tuple[str, ...]) -> tuple[IPNetwork, ...]:
    """Parse IPs/CIDRs (e.g. "10.0.0.0/8", "127.0.0.1"); raises ValueError on bad input."""
    return tuple(ipaddress.ip_network(entry, strict=False) for entry in entries)


def _is_trusted(ip: str, trusted: Iterable[IPNetwork]) -> bool:
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(address in network for network in trusted)


def resolve_client_ip(
    peer_ip: str | None, forwarded_for: str | None, trusted: tuple[IPNetwork, ...]
) -> str:
    """Return the originating client IP.

    X-Forwarded-For is client-controlled, so it is only consulted when the direct peer is a
    trusted proxy. The chain is then walked right-to-left (each proxy appends the address it
    saw), skipping trusted proxies; the first untrusted hop is the real client. Anything a
    client prepends to the header itself is therefore ignored.
    """
    peer = peer_ip or "unknown"
    if not forwarded_for or not _is_trusted(peer, trusted):
        return peer

    hops = [hop.strip() for hop in forwarded_for.split(",") if hop.strip()]
    for hop in reversed(hops):
        if not _is_trusted(hop, trusted):
            return hop
    return hops[0] if hops else peer
