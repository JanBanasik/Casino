import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def _register_and_login(client: TestClient, username: str = "testuser") -> str:
    client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "password123",
        },
    )
    res = client.post(
        "/api/auth/login",
        json={"username": username, "password": "password123"},
    )
    assert res.status_code == 200
    return res.json()["access_token"]
