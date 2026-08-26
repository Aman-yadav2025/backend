from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Database (SQLAlchemy async, e.g. Supabase connection string) ------
    # postgresql+asyncpg://user:password@host:5432/dbname
    database_url: SecretStr

    # --- Clerk ---------------------------------------------------------------
    # JWKS endpoint from your Clerk instance, e.g.
    # https://<your-clerk-frontend-api>.clerk.accounts.dev/.well-known/jwks.json
    clerk_jwks_url: str
    clerk_issuer: str
    # Signing secret for Clerk webhooks (svix), starts with "whsec_"
    clerk_webhook_secret: SecretStr
    clerk_secret_key: SecretStr | None = None

    # --- Razorpay --------------------------------------------------------------
    razorpay_key_id: str
    razorpay_key_secret: SecretStr
    razorpay_webhook_secret: SecretStr

    # --- Cloudflare R2 (S3-compatible) -----------------------------------------
    r2_account_id: str
    r2_access_key_id: str
    r2_secret_access_key: SecretStr
    r2_bucket_name: str
    r2_endpoint_url: str  # https://<account_id>.r2.cloudflarestorage.com
    r2_presigned_url_expiry_seconds: int = 900
    r2_max_upload_bytes: int = 50 * 1024 * 1024  # 50 MB default cap

    # --- Redis (rate limiter shared store) ------------------------------------
    redis_url: str = "redis://localhost:6379"

    # --- App ---------------------------------------------------------------
    environment: str = "development"
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
