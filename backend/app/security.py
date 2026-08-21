import asyncio
import uuid

import jwt
from fastapi import Depends, Header, HTTPException, status, Path
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWK
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Company, CompanyMember, CompanyType, MemberRole, MemberStatus, Profile, SystemRole

bearer_scheme = HTTPBearer(auto_error=False)

import time
import httpx

class SafeJWKSClient:
    def __init__(self, jwks_url: str, ttl: int = 300):
        self.jwks_url = jwks_url
        self.ttl = ttl
        self._keys = {}
        self._last_fetched = 0.0
        self._fetch_failed = False
        self._lock = None
        
    async def get_signing_key_from_jwt(self, token: str):
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        if not kid:
            raise jwt.PyJWTError("Missing 'kid' in token header")

        now = time.monotonic()
        
        # Fast path: Grab a local reference for lock-free thread safety
        current_keys = self._keys
        jwk = current_keys.get(kid)
        
        if jwk and (now - self._last_fetched < self.ttl):
            return jwk

        if self._lock is None:
            self._lock = asyncio.Lock()

        async with self._lock:
            current_time = time.monotonic()
            needs_fetch = False
            
            # We must fetch if we don't have the kid (key rotation), OR if the cache is stale.
            # To prevent cache-miss DoS storms, we aggressively throttle fetches to max 1 per 5 seconds.
            if kid not in self._keys:
                if current_time - self._last_fetched >= 5.0:
                    needs_fetch = True
            elif current_time - self._last_fetched >= self.ttl:
                needs_fetch = True
                
            if needs_fetch:
                self._fetch_failed = True  # Assume failure to protect against CancelledError mid-flight
                try:
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(self.jwks_url, timeout=10.0)
                        resp.raise_for_status()
                        data = resp.json()
                        
                        if "keys" in data:
                            new_keys = {}
                            for key_data in data["keys"]:
                                k = key_data.get("kid")
                                if k:
                                    try:
                                        parsed_jwk = PyJWK(key_data)
                                        new_keys[k] = parsed_jwk
                                    except Exception:
                                        pass
                            
                            self._keys = new_keys
                        self._fetch_failed = False
                except Exception as exc:
                    if not self._keys:
                        raise RuntimeError(f"Clerk JWKS fetch failed: {exc}") from exc
                finally:
                    # CRITICAL: Always update _last_fetched, even on asyncio.CancelledError (which inherits from BaseException).
                    # If a client disconnects, FastAPI cancels the task. If we don't update this timestamp, the next task 
                    # in the lock queue will instantly re-trigger a fetch, causing a Thundering Herd DoS on Clerk.
                    self._last_fetched = time.monotonic()

            # We are still inside the lock! We have the absolute latest, perfectly synchronized state.
            if not self._keys:
                if self._fetch_failed:
                    # If cache is empty and fetch failed, network is down.
                    raise RuntimeError("Clerk JWKS cache is empty and fetch failed")
                else:
                    # If cache is empty but fetch succeeded, Clerk explicitly revoked all keys!
                    raise jwt.PyJWTError("Clerk JWKS returned 0 valid keys. All tokens invalid.")

            jwk = self._keys.get(kid)
            if not jwk:
                if self._fetch_failed:
                    # The cache is in a failed state (network is down). We cannot verify if this kid is valid.
                    # Returning 401 would prematurely log the user out on the frontend.
                    # Return 502 Bad Gateway to preserve the user's session during the outage.
                    raise RuntimeError(f"Authentication provider unreachable. Cannot verify new Key ID {kid}")
                else:
                    raise jwt.PyJWTError(f"Key ID {kid} not found in JWKS")
                
            return jwk

# Cached JWKS client — strictly TTL cached to prevent cache-miss DoS.
_jwks_client = SafeJWKSClient(settings.clerk_jwks_url)


async def verify_clerk_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    try:
        # JWKS client fetches keys asynchronously over the network.
        signing_key = await _jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=settings.clerk_issuer,
            options={"verify_aud": False},  # Clerk session tokens don't set aud by default
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Authentication provider unavailable") from exc
    return payload


async def get_current_profile(
    token_payload: dict = Depends(verify_clerk_token),
    db: AsyncSession = Depends(get_db),
) -> Profile:
    clerk_user_id = token_payload.get("sub")
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Token missing subject claim")

    result = await db.execute(select(Profile).where(Profile.id == clerk_user_id))
    profile = result.scalar_one_or_none()
    if profile is None:
        # Clerk webhooks provision profiles asynchronously; this can happen
        # briefly right after signup.
        raise HTTPException(
            status_code=404,
            detail="Profile not provisioned yet. Please retry shortly.",
        )
    return profile


def require_system_roles(*roles: SystemRole):
    async def dependency(profile: Profile = Depends(get_current_profile)) -> Profile:
        if profile.system_role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions for this action")
        return profile

    return dependency


async def get_membership_or_403(
    company_id: uuid.UUID,
    profile: Profile,
    db: AsyncSession,
) -> CompanyMember:
    if profile.system_role == SystemRole.PLATFORM_ADMIN:
        # Platform Admins have global access to all companies, but we must still ensure the company exists
        company = await db.scalar(select(Company).where(Company.id == company_id, Company.deleted_at.is_(None)))
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found")
        return CompanyMember(
            company_id=company_id,
            profile_id=profile.id,
            member_role=MemberRole.OWNER,
            status=MemberStatus.ACTIVE,
        )

    result = await db.execute(
        select(CompanyMember)
        .join(Company, Company.id == CompanyMember.company_id)
        .where(
            CompanyMember.company_id == company_id,
            CompanyMember.profile_id == profile.id,
            CompanyMember.status == MemberStatus.ACTIVE,
            Company.deleted_at.is_(None),
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=403, detail="Not an active member of this company")
    return membership


async def require_active_company_membership(
    company_id: uuid.UUID = Path(...),
    profile: Profile = Depends(get_current_profile),
    db: AsyncSession = Depends(get_db),
) -> CompanyMember:
    return await get_membership_or_403(company_id, profile, db)


async def require_company_admin(
    membership: CompanyMember = Depends(require_active_company_membership),
) -> CompanyMember:
    if membership.member_role != MemberRole.OWNER:
        raise HTTPException(status_code=403, detail="Company admin (OWNER) access required")
    return membership





require_platform_admin = require_system_roles(SystemRole.PLATFORM_ADMIN)
