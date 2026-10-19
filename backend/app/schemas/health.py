from typing import Literal

from pydantic import BaseModel


class HealthReport(BaseModel):
    status: Literal["ok", "degraded", "unhealthy"]
    database: Literal["ok", "error"]
    redis: Literal["ok", "error"]
