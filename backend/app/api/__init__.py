from fastapi import APIRouter

from app.api.routes_auth import router as auth_router
from app.api.routes_health import router as health_router
from app.api.routes_roulette import router as roulette_router
from app.api.routes_sessions import router as sessions_router
from app.api.routes_wallet import router as wallet_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(wallet_router, prefix="/wallet", tags=["wallet"])
api_router.include_router(sessions_router, prefix="/sessions", tags=["sessions"])
api_router.include_router(roulette_router, prefix="/roulette", tags=["roulette"])
