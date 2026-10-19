from fastapi import APIRouter, Depends, Response, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.db.session import get_db
from app.schemas.health import HealthReport
from app.services.health_service import build_health_report

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthReport)
async def health(
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> HealthReport:
    report = await build_health_report(db, redis)
    if report.status == "unhealthy":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return report
