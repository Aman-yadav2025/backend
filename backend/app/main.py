from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import admin, clerk_webhooks, companies, company_members, documents, payments, promo_codes, razorpay_webhooks, profiles

app = FastAPI(title="Platform API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(clerk_webhooks.router)
app.include_router(razorpay_webhooks.router)
app.include_router(companies.router)
app.include_router(company_members.router)
app.include_router(documents.router)
app.include_router(promo_codes.router)
app.include_router(payments.router)
app.include_router(admin.router)
app.include_router(profiles.router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "environment": settings.environment}
