from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import get_settings
from app.core.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip_and_salting() -> None:
    first = hash_password("s3cret-pass")
    second = hash_password("s3cret-pass")

    assert first != second  # unique salt per hash
    assert first.startswith("$argon2id$")
    assert verify_password("s3cret-pass", first)
    assert not verify_password("wrong-pass", first)


def test_verify_password_rejects_garbage_hash() -> None:
    assert not verify_password("anything", "not-a-hash")


def test_access_token_roundtrip() -> None:
    token = create_access_token(42)

    assert decode_access_token(token.token) == 42
    assert token.expires_in == get_settings().access_token_expire_minutes * 60


def test_expired_token_is_rejected() -> None:
    long_ago = datetime.now(UTC) - timedelta(days=2)
    token = create_access_token(1, now=long_ago)

    with pytest.raises(InvalidTokenError):
        decode_access_token(token.token)


def test_tampered_token_is_rejected() -> None:
    token = create_access_token(1).token
    header, payload, signature = token.split(".")
    tampered = f"{header}.{payload}.{signature[::-1]}"

    with pytest.raises(InvalidTokenError):
        decode_access_token(tampered)


def test_token_signed_with_other_key_is_rejected() -> None:
    now = datetime.now(UTC)
    forged = jwt.encode(
        {"sub": "1", "type": "access", "iat": now, "exp": now + timedelta(hours=1)},
        "attacker-key-that-is-at-least-32-bytes-long",
        algorithm="HS256",
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(forged)


def test_unsigned_alg_none_token_is_rejected() -> None:
    now = datetime.now(UTC)
    unsigned = jwt.encode(
        {"sub": "1", "type": "access", "iat": now, "exp": now + timedelta(hours=1)},
        key=None,
        algorithm="none",
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(unsigned)


def test_token_with_wrong_type_or_subject_is_rejected() -> None:
    secret = get_settings().jwt_secret_key.get_secret_value()
    now = datetime.now(UTC)
    base = {"iat": now, "exp": now + timedelta(hours=1)}

    wrong_type = jwt.encode({**base, "sub": "1", "type": "refresh"}, secret, algorithm="HS256")
    bad_subject = jwt.encode({**base, "sub": "abc", "type": "access"}, secret, algorithm="HS256")

    for token in (wrong_type, bad_subject):
        with pytest.raises(InvalidTokenError):
            decode_access_token(token)
