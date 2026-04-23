from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import api_router
from app.api.ws_table import router as ws_router
from app.core.config import settings
from app.db.redis_client import init_redis, shutdown_redis
from app.db.session import init_db_engine, shutdown_db_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db_engine()
    await init_redis()
    yield
    await shutdown_redis()
    await shutdown_db_engine()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(api_router, prefix="/api")
app.include_router(ws_router)
