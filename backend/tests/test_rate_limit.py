"""Rate-limiting integration test — needs the app (DB/Redis) via the client fixture."""
import pytest

from app.core.limiter import limiter


@pytest.mark.integration
def test_login_route_is_rate_limited(client):
    # The limiter uses shared in-memory state — start from a clean slate.
    limiter.reset()

    # /login is capped at 10/minute. The 11th request from the same client
    # must be rejected with HTTP 429 before reaching the handler.
    statuses = []
    for _ in range(11):
        res = client.post(
            "/api/auth/login",
            json={"username": "nobody", "password": "whatever"},
        )
        statuses.append(res.status_code)

    assert 429 in statuses
    # The first request must not be rate-limited.
    assert statuses[0] != 429
    assert statuses[-1] == 429

    limiter.reset()  # avoid leaking the exhausted counter into other tests
