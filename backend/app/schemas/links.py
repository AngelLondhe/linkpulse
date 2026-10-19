from datetime import UTC, datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field, model_validator

from app.models import Link
from app.utils.url_validation import MAX_URL_LENGTH

# Destination URLs are fully validated in the service layer (it needs the app's own host to
# block redirect loops); the schemas only bound their size.


class LinkCreate(BaseModel):
    url: str = Field(min_length=1, max_length=MAX_URL_LENGTH)
    custom_alias: str | None = Field(
        default=None, max_length=64, description="Optional custom short code (3-30 chars)"
    )
    expires_at: AwareDatetime | None = Field(
        default=None, description="Link stops working at this instant (must include a TZ)"
    )
    max_clicks: int | None = Field(default=None, ge=1, le=1_000_000_000)


class LinkUpdate(BaseModel):
    """Partial update. For expires_at / max_clicks an explicit null clears the limit."""

    url: str | None = Field(default=None, min_length=1, max_length=MAX_URL_LENGTH)
    is_active: bool | None = None
    expires_at: AwareDatetime | None = None
    max_clicks: int | None = Field(default=None, ge=1, le=1_000_000_000)

    @model_validator(mode="after")
    def _at_least_one_field(self) -> "LinkUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update")
        return self


LinkStatus = Literal["active", "paused", "expired", "limit_reached"]


def link_status(link: Link, total_clicks: int, now: datetime | None = None) -> LinkStatus:
    if not link.is_active:
        return "paused"
    if link.expires_at is not None and link.expires_at <= (now or datetime.now(UTC)):
        return "expired"
    if link.max_clicks is not None and total_clicks >= link.max_clicks:
        return "limit_reached"
    return "active"


class LinkRead(BaseModel):
    id: int
    short_code: str
    short_url: str
    original_url: str
    is_custom: bool
    is_active: bool
    expires_at: datetime | None
    max_clicks: int | None
    has_password: bool
    total_clicks: int
    status: LinkStatus
    created_at: datetime

    @classmethod
    def from_model(cls, link: Link, *, total_clicks: int, base_url: str) -> "LinkRead":
        return cls(
            id=link.id,
            short_code=link.short_code,
            short_url=f"{base_url.rstrip('/')}/{link.short_code}",
            original_url=link.original_url,
            is_custom=link.is_custom,
            is_active=link.is_active,
            expires_at=link.expires_at,
            max_clicks=link.max_clicks,
            has_password=link.password_hash is not None,
            total_clicks=total_clicks,
            status=link_status(link, total_clicks),
            created_at=link.created_at,
        )


class LinkPage(BaseModel):
    items: list[LinkRead]
    total: int
    page: int
    page_size: int
