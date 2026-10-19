from sqlalchemy.exc import IntegrityError

from app.utils.db_errors import is_unique_violation


class _DriverError(Exception):
    def __init__(self, constraint_name: str) -> None:
        super().__init__(constraint_name)
        self.constraint_name = constraint_name


class _AdaptedError(Exception):
    def __init__(self, sqlstate: str, constraint_name: str) -> None:
        super().__init__(sqlstate)
        self.sqlstate = sqlstate
        self.__cause__ = _DriverError(constraint_name)


def _integrity_error(sqlstate: str, constraint: str) -> IntegrityError:
    return IntegrityError("INSERT ...", {}, _AdaptedError(sqlstate, constraint))


def test_matches_unique_violation_on_named_constraint() -> None:
    exc = _integrity_error("23505", "ix_links_short_code")

    assert is_unique_violation(exc)
    assert is_unique_violation(exc, "ix_links_short_code")


def test_ignores_other_constraints_and_error_types() -> None:
    other_unique = _integrity_error("23505", "uq_users_email")
    foreign_key = _integrity_error("23503", "fk_links_user_id_users")

    assert not is_unique_violation(other_unique, "ix_links_short_code")
    assert not is_unique_violation(foreign_key)
