from fastapi import APIRouter

from pribilka.api.v1 import alerts, analytics, bonds, deposits, fx, gold, notifications

api_router = APIRouter()
api_router.include_router(deposits.router, prefix="/deposits", tags=["deposits"])
api_router.include_router(bonds.router, prefix="/bonds", tags=["bonds"])
api_router.include_router(gold.router, prefix="/gold", tags=["gold"])
api_router.include_router(fx.router, prefix="/fx", tags=["fx"])
api_router.include_router(analytics.router, tags=["analytics"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
