"""Validation for user-chosen short codes (custom aliases)."""

import re

ALIAS_PATTERN = re.compile(r"[a-zA-Z0-9_-]{3,30}")

# Paths the app (or a future version of it) may need, and words that invite phishing.
RESERVED_ALIASES = frozenset(
    {
        "about", "account", "admin", "api", "app", "assets", "auth", "billing", "blog",
        "dashboard", "docs", "favicon", "health", "healthz", "help", "home", "index",
        "links", "login", "logout", "metrics", "null", "openapi", "pricing", "privacy",
        "qr", "redoc", "register", "root", "security", "settings", "signin", "signup",
        "static", "stats", "status", "support", "terms", "undefined", "www",
    }
)  # fmt: skip


class InvalidAliasError(ValueError):
    """Raised with a human-readable reason when an alias is not allowed."""


def validate_alias(alias: str) -> str:
    """Return the alias if usable, else raise InvalidAliasError.

    Aliases are case-sensitive like generated codes, but the reserved-word check is not,
    so "Admin" or "LOGIN" are rejected too.
    """
    if not ALIAS_PATTERN.fullmatch(alias):
        raise InvalidAliasError("Alias must be 3-30 characters: letters, digits, '-' or '_'")
    if alias.lower() in RESERVED_ALIASES:
        raise InvalidAliasError(f"'{alias}' is a reserved word")
    return alias
