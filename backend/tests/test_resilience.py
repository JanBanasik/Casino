"""Unit tests for the resilience decorators (no DB/Redis needed)."""
import pytest

from app.db.resilience import db_resilient, redis_resilient


@pytest.mark.asyncio
async def test_redis_resilient_falls_back_to_none_on_persistent_failure():
    calls = {"n": 0}

    @redis_resilient
    async def always_down():
        calls["n"] += 1
        raise ConnectionError("redis down")

    # Non-critical: degrades to None instead of raising, after retrying.
    assert await always_down() is None
    assert calls["n"] > 1  # retried at least once


@pytest.mark.asyncio
async def test_redis_resilient_returns_value_when_healthy():
    @redis_resilient
    async def ok():
        return "pong"

    assert await ok() == "pong"


@pytest.mark.asyncio
async def test_db_resilient_retries_then_succeeds_on_transient_failure():
    calls = {"n": 0}

    @db_resilient
    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("transient")
        return "committed"

    assert await flaky() == "committed"
    assert calls["n"] == 3  # two failures, third attempt succeeds


@pytest.mark.asyncio
async def test_db_resilient_reraises_after_exhausting_retries():
    calls = {"n": 0}

    @db_resilient
    async def always_down():
        calls["n"] += 1
        raise ConnectionError("db down")

    # Critical writes must not silently swallow failures.
    with pytest.raises(Exception):
        await always_down()
    assert calls["n"] > 1
