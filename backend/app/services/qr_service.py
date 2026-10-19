"""QR codes for short links."""

import io
from dataclasses import dataclass
from typing import Literal

import segno

QRFormat = Literal["png", "svg"]
MEDIA_TYPES: dict[QRFormat, str] = {"png": "image/png", "svg": "image/svg+xml"}


@dataclass(frozen=True)
class QRImage:
    content: bytes
    media_type: str
    filename: str


def render_qr(url: str, *, fmt: QRFormat, scale: int, filename_stem: str) -> QRImage:
    """Encode ``url`` as a QR code (error correction "M", quiet zone of 4 modules)."""
    qr = segno.make(url, error="m", micro=False)
    buffer = io.BytesIO()
    if fmt == "svg":
        qr.save(buffer, kind="svg", scale=scale, border=4, xmldecl=False, svgns=True)
    else:
        qr.save(buffer, kind="png", scale=scale, border=4)
    return QRImage(
        content=buffer.getvalue(),
        media_type=MEDIA_TYPES[fmt],
        filename=f"{filename_stem}-qr.{fmt}",
    )
