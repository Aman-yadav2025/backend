from fastapi import FastAPI, Request
import logging
import traceback
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.config import settings
from app.rate_limit import limiter
from app.routers import admin, clerk_webhooks, companies, company_members, documents, kpis, marketplace, payments, promo_codes, razorpay_webhooks, profiles, brand_marketplace, recycler_kpis, collector_purchases, marketplace_overview, withdrawals
app = FastAPI(title="Platform API", version="1.0.0")

# ── Rate limiter state ────────────────────────────────────────────────────────
# Attach the limiter instance to app state so SlowAPIMiddleware can find it.
app.state.limiter = limiter

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Log the full traceback server-side — never send it to the client.
    logging.exception("Unhandled exception on %s %s", request.method, request.url)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred."},
    )

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return a clean 429 instead of a 500 when a limit fires."""
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please slow down and try again later."},
    )

# ── Middleware stack (applied innermost-first, so register outermost-first) ───
#
# Execution order on an incoming request:
#   1. ProxyHeadersMiddleware  — resolves real client IP from Cloudflare headers
#   2. SlowAPIMiddleware       — checks the rate limit using that real IP
#   3. CORSMiddleware          — sets CORS response headers
#
# IMPORTANT: Starlette applies middlewares in REVERSE registration order.
# We register outermost (ProxyHeaders) LAST so it wraps everything below it.

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# SlowAPI intercepts every request and enforces the rate limits.
app.add_middleware(SlowAPIMiddleware)

# Trusts CF-Connecting-IP / X-Forwarded-For from Cloudflare's proxy layer.
# trusted_hosts="*" is safe here because our _get_real_client_ip() in
# rate_limit.py reads CF-Connecting-IP exclusively (which Cloudflare controls),
# not the raw X-Forwarded-For that a client could spoof.
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

# ── Routers ───────────────────────────────────────────────────────────────────
# Webhook routers are intentionally first. They use Cloudflare-bypassed IPs
# from known providers and already validate signatures before any DB work.
app.include_router(clerk_webhooks.router)
app.include_router(razorpay_webhooks.router)
app.include_router(companies.router)
app.include_router(company_members.router)
app.include_router(documents.router)
app.include_router(kpis.router)
app.include_router(promo_codes.router)
app.include_router(payments.router)
app.include_router(admin.router)
app.include_router(profiles.router)
app.include_router(marketplace.router)
app.include_router(brand_marketplace.router)
app.include_router(recycler_kpis.router)
app.include_router(collector_purchases.router)
app.include_router(marketplace_overview.router)
app.include_router(withdrawals.router)

@app.get("/health")
async def health_check():
    return {"status": "ok", "environment": settings.environment}
