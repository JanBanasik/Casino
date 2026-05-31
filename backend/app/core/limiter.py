from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def client_ip(request: Request) -> str:
    """Real client IP behind a reverse proxy.

    Prefers the left-most address in ``X-Forwarded-For`` (the original client),
    falls back to ``X-Real-IP``, then to the direct peer address. Without this
    every request behind the nginx proxy shares the proxy's single IP and is
    rate-limited as one bucket.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return get_remote_address(request)


limiter = Limiter(key_func=client_ip)
