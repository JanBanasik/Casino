from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes_health import router as health_router

app = FastAPI()
app.include_router(health_router, prefix="/api")


async def test_health_ok():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
