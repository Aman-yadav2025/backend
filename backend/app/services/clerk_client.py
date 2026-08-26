import urllib.parse
import httpx

from app.config import settings

_CLERK_BASE = "https://api.clerk.com/v1"
_TIMEOUT = 10.0  # seconds — keep short; these calls are made while holding DB locks


class ClerkAPIError(Exception):
    pass


async def _clerk_delete(path: str) -> None:
    """
    Issues an authenticated DELETE to the Clerk REST API.
    Treats 404 as success (idempotent — resource already gone).
    Raises ClerkAPIError for any other non-2xx response.
    """
    if not settings.clerk_secret_key:
        raise ClerkAPIError("CLERK_SECRET_KEY is not configured")

    url = f"{_CLERK_BASE}/{path}"
    headers = {"Authorization": f"Bearer {settings.clerk_secret_key.get_secret_value()}"}

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.delete(url, headers=headers)
        if response.status_code not in (200, 404):
            raise ClerkAPIError(f"Clerk DELETE {path} failed [{response.status_code}]: {response.text}")


async def _clerk_patch(path: str, json_data: dict) -> None:
    """
    Issues an authenticated PATCH to the Clerk REST API.
    Raises ClerkAPIError for non-2xx responses.
    """
    if not settings.clerk_secret_key:
        raise ClerkAPIError("CLERK_SECRET_KEY is not configured")

    url = f"{_CLERK_BASE}/{path}"
    headers = {"Authorization": f"Bearer {settings.clerk_secret_key.get_secret_value()}"}

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.patch(url, headers=headers, json=json_data)
        if response.status_code not in (200, 201, 204):
            raise ClerkAPIError(f"Clerk PATCH {path} failed [{response.status_code}]: {response.text}")


async def delete_user(user_id: str) -> None:
    """Deletes a user from Clerk via their REST API."""
    safe_id = urllib.parse.quote(user_id, safe="")
    await _clerk_delete(f"users/{safe_id}")


async def delete_organization(org_id: str) -> None:
    """Deletes an organization from Clerk via their REST API."""
    safe_id = urllib.parse.quote(org_id, safe="")
    await _clerk_delete(f"organizations/{safe_id}")


async def remove_organization_membership(org_id: str, user_id: str) -> None:
    """Removes a user from an organization in Clerk via their REST API."""
    safe_org = urllib.parse.quote(org_id, safe="")
    safe_user = urllib.parse.quote(user_id, safe="")
    await _clerk_delete(f"organizations/{safe_org}/memberships/{safe_user}")


async def update_organization_membership(org_id: str, user_id: str, role: str) -> None:
    """Updates a user's role in an organization in Clerk via their REST API."""
    safe_org = urllib.parse.quote(org_id, safe="")
    safe_user = urllib.parse.quote(user_id, safe="")
    await _clerk_patch(f"organizations/{safe_org}/memberships/{safe_user}", {"role": role})

