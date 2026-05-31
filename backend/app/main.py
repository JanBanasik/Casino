from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api import api_router
from app.api.ws_poker import router as ws_poker_router
from app.api.ws_table import router as ws_router
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import setup_logging
from app.db.redis_client import init_redis, shutdown_redis
from app.db.session import init_db_engine, shutdown_db_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.debug)
    logger.info("Starting up {}", settings.app_name)
    init_db_engine()
    await init_redis()
    yield
    logger.info("Shutting down")
    await shutdown_redis()
    await shutdown_db_engine()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# ── Middleware ──────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# ── Exception handlers ──────────────────────────────────────────────────────
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on {} {}", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ── Routers ─────────────────────────────────────────────────────────────────
app.include_router(api_router, prefix="/api")
app.include_router(ws_router)
app.include_router(ws_poker_router)
