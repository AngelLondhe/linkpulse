"""Random Base62 short codes."""

import secrets
import string

BASE62_ALPHABET = string.digits + string.ascii_lowercase + string.ascii_uppercase
CODE_LENGTH = 7  # 62**7 ≈ 3.5 trillion codes


def generate_short_code(length: int = CODE_LENGTH) -> str:
    """Return a cryptographically random Base62 code (unguessable, not sequential)."""
    return "".join(secrets.choice(BASE62_ALPHABET) for _ in range(length))
