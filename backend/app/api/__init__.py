from fastapi import APIRouter

from app.api.routes_auth import router as auth_router
from app.api.routes_config import router as config_router
from app.api.routes_health import router as health_router
from app.api.routes_notifications import router as notifications_router
from app.api.routes_payments import router as payments_router
from app.api.routes_roulette import router as roulette_router
from app.api.routes_sessions import router as sessions_router
from app.api.routes_wallet import router as wallet_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(wallet_router, prefix="/wallet", tags=["wallet"])
api_router.include_router(sessions_router, prefix="/sessions", tags=["sessions"])
api_router.include_router(roulette_router, prefix="/roulette", tags=["roulette"])
api_router.include_router(notifications_router, prefix="/notifications", tags=["notifications"])
api_router.include_router(payments_router, prefix="/payments", tags=["payments"])
api_router.include_router(config_router, prefix="/config", tags=["config"])
