import re

from app.utils.ip_hash import hash_ip


def test_hash_is_deterministic_hex_sha256() -> None:
    digest = hash_ip("203.0.113.9", "salt-a")

    assert digest == hash_ip("203.0.113.9", "salt-a")
    assert re.fullmatch(r"[0-9a-f]{64}", digest)


def test_salt_and_ip_both_change_the_hash() -> None:
    base = hash_ip("203.0.113.9", "salt-a")

    assert hash_ip("203.0.113.9", "salt-b") != base
    assert hash_ip("203.0.113.10", "salt-a") != base


def test_raw_ip_is_not_recoverable_from_output() -> None:
    assert "203.0.113.9" not in hash_ip("203.0.113.9", "salt-a")


def test_surrounding_whitespace_is_ignored() -> None:
    assert hash_ip(" 2001:db8::1 ", "s") == hash_ip("2001:db8::1", "s")
