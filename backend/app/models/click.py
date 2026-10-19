from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Click(Base):
    """One redirect event, written in bulk by the worker (never in the request path)."""

    __tablename__ = "clicks"
    __table_args__ = (
        # Serves both "clicks for link X" (leftmost prefix) and "clicks for link X in a date
        # range" (the stats queries), so a separate single-column link_id index is redundant.
        Index("ix_clicks_link_id_clicked_at", "link_id", "clicked_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    link_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("links.id", ondelete="CASCADE"))
    clicked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    referrer: Mapped[str | None] = mapped_column(String(2048))
    browser: Mapped[str] = mapped_column(String(64))
    os: Mapped[str] = mapped_column(String(64))
    device_type: Mapped[str] = mapped_column(String(16))
    # ISO 3166-1 alpha-2 code (e.g. "US"); NULL when unknown. The API renders NULL as "Unknown".
    country: Mapped[str | None] = mapped_column(String(2))
    city: Mapped[str | None] = mapped_column(String(128))
    # Salted SHA-256 hex digest of the client IP. Raw IPs are never stored.
    ip_hash: Mapped[str] = mapped_column(String(64))
