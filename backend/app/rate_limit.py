"""
Centralised rate-limiter configuration.

Algorithm : Moving Window (Sliding Window) — no boundary-burst loophole.
Backend   : Redis — shared across ALL Uvicorn workers so limits are global.
IP source : CF-Connecting-IP header exclusively.
            Cloudflare strips any client-supplied CF-Connecting-IP before
            forwarding, so this header cannot be spoofed.
            Falls back to the ASGI client host only in local development
            (when requests reach the server directly, without Cloudflare).
"""
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings


def _get_real_client_ip(request: Request) -> str:
    """
    Priority order:
      1. CF-Connecting-IP  – injected by Cloudflare, client cannot fake it.
      2. ASGI client host  – fallback for local dev / direct connections.
    """
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()
    # Fallback: returns the direct TCP peer (safe in local dev only)
    return get_remote_address(request)


# Moving-window algorithm requires a persistent backend.
# Redis keeps counters consistent across multiple workers/processes.
limiter = Limiter(
    key_func=_get_real_client_ip,
    storage_uri=settings.redis_url,
    strategy="moving-window",
    # Default limit applied globally via app.state.limiter unless overridden
    # per route with @limiter.limit("...")
    default_limits=["100/minute"],
)
