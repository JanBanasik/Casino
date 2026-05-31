from pyresilience import CircuitBreakerConfig, FallbackConfig, RetryConfig, TimeoutConfig, resilient

# Applied to critical DB writes — retries transient connection errors,
# opens circuit after 5 failures so the app degrades gracefully instead of flooding.
db_resilient = resilient(
    retry=RetryConfig(max_attempts=4, delay=0.5, backoff_factor=2.0),
    timeout=TimeoutConfig(seconds=8),
    circuit_breaker=CircuitBreakerConfig(failure_threshold=5, recovery_timeout=30),
)

# Applied to Redis — non-critical, falls back to None so the app keeps running
# even when Redis is temporarily unavailable.
redis_resilient = resilient(
    retry=RetryConfig(max_attempts=3, delay=0.3, backoff_factor=1.5),
    timeout=TimeoutConfig(seconds=3),
    fallback=FallbackConfig(handler=lambda e: None),
)
