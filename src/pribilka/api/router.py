from fastapi import APIRouter

from pribilka.api.v1 import (
    admin,
    alerts,
    analytics,
    bonds,
    deposits,
    devices,
    fx,
    gold,
    insights,
    notifications,
    trends,
)

api_router = APIRouter()

market_router = APIRouter(prefix="/markets/{country}")
market_router.include_router(deposits.router, prefix="/deposits", tags=["deposits"])
market_router.include_router(bonds.router, prefix="/bonds", tags=["bonds"])
market_router.include_router(gold.router, prefix="/gold", tags=["gold"])
market_router.include_router(fx.router, prefix="/fx", tags=["fx"])
market_router.include_router(analytics.router, tags=["analytics"])
market_router.include_router(trends.router, prefix="/trends", tags=["trends"])
market_router.include_router(insights.router, prefix="/insights", tags=["insights"])

api_router.include_router(market_router, tags=["markets"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(devices.router, prefix="/devices", tags=["devices"])
