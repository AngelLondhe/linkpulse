"""ORM models. Importing this package registers every table on ``Base.metadata``."""

from app.models.click import Click
from app.models.link import Link
from app.models.user import User

__all__ = ["Click", "Link", "User"]
