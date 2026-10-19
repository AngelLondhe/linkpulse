"""Helpers for interpreting database errors raised through SQLAlchemy + asyncpg."""

from sqlalchemy.exc import IntegrityError

UNIQUE_VIOLATION = "23505"


def is_unique_violation(exc: IntegrityError, constraint: str | None = None) -> bool:
    """True if ``exc`` is a unique violation (optionally on a specific constraint/index)."""
    if getattr(exc.orig, "sqlstate", None) != UNIQUE_VIOLATION:
        return False
    if constraint is None:
        return True
    driver_error = getattr(exc.orig, "__cause__", None)
    return getattr(driver_error, "constraint_name", None) == constraint
