"""Privacy-preserving IP fingerprints."""

import hashlib
import hmac


def hash_ip(ip: str, salt: str) -> str:
    """Return a salted SHA-256 (HMAC-SHA256, keyed by the secret salt) hex digest of ``ip``.

    Lets us count unique visitors without storing addresses. The salt is a server secret:
    without it the IPv4 space is small enough to brute-force, so it must never be committed.
    """
    return hmac.new(salt.encode(), ip.strip().encode(), hashlib.sha256).hexdigest()
