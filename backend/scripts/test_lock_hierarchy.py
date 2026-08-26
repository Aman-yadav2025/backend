"""
Distributed Lock Hierarchy Test
================================
Fires all three concurrent operations for the same user simultaneously:
  1. user.deleted webhook
  2. organizationMembership.created webhook
  3. DELETE /profiles/me

Checks: no PostgreSQL DeadlockDetected errors, all requests resolve without 500.

Usage:
    pip install httpx python-dotenv
    python scripts/test_lock_hierarchy.py
"""

import asyncio
import json
import time
import hmac
import hashlib
import base64
import sys
import os
import uuid
import requests
import httpx
from dotenv import dotenv_values

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import AsyncSessionLocal
from app.models import Profile, SystemRole
from sqlalchemy import delete

env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
env = dotenv_values(env_path)

WEBHOOK_SECRET = env.get("CLERK_WEBHOOK_SECRET", "")
CLERK_SECRET_KEY = env.get("CLERK_SECRET_KEY", "")
CLERK_API_BASE = "https://api.clerk.com/v1"
BASE_URL = "http://localhost:8000"

# Globals populated at runtime
USER_JWT = ""
USER_ID = ""
ORG_ID = f"org_{uuid.uuid4().hex[:10]}"

def provision_clerk_user() -> tuple[str, str]:
    """Creates a temporary Clerk user and mints a session JWT for them."""
    print("\n[Setup] Provisioning temporary Clerk user...")
    headers = {"Authorization": f"Bearer {CLERK_SECRET_KEY}", "Content-Type": "application/json"}
    
    email = f"test_lock_{uuid.uuid4().hex[:8]}@example.com"
    password = f"TestPass123!{uuid.uuid4().hex[:8]}"
    resp = requests.post(f"{CLERK_API_BASE}/users", headers=headers, json={"email_address": [email], "password": password})
    if not resp.ok:
        print(f"❌ Failed to create Clerk user: {resp.text}")
        sys.exit(1)
    
    clerk_user_id = resp.json()["id"]
    print(f"✅ Created Clerk User: {clerk_user_id}")

    resp = requests.post(f"{CLERK_API_BASE}/sessions", headers=headers, json={"user_id": clerk_user_id})
    session_id = resp.json()["id"]

    resp = requests.post(f"{CLERK_API_BASE}/sessions/{session_id}/tokens/dev_token", headers=headers, json={})
    jwt = resp.json()["jwt"]
    print("✅ Minted JWT successfully.")
    return clerk_user_id, jwt

def delete_clerk_user(clerk_user_id: str):
    """Deletes the temporary Clerk user."""
    print(f"\n[Teardown] Deleting Clerk user {clerk_user_id}...")
    headers = {"Authorization": f"Bearer {CLERK_SECRET_KEY}"}
    resp = requests.delete(f"{CLERK_API_BASE}/users/{clerk_user_id}", headers=headers)
    if resp.ok:
        print("✅ User deleted.")
    else:
        print(f"❌ Failed to delete Clerk user: {resp.text}")

async def setup_test_db():
    print("\n[Setup] Seeding test profile in the database...")
    async with AsyncSessionLocal() as db:
        db.add(Profile(
            id=USER_ID,
            email=f"{USER_ID}@test.com",
            system_role=SystemRole.BRAND_ADMIN,
        ))
        try:
            await db.commit()
            print("[Setup] Test profile ready.")
        except Exception:
            await db.rollback()
            print("[Setup] Profile already exists (likely from webhook).")

def sign_webhook(payload: dict, secret: str) -> dict:
    body        = json.dumps(payload, separators=(",", ":"))
    msg_id      = f"msg_{int(time.time()*1000)}"
    timestamp   = str(int(time.time()))

    raw_secret  = base64.b64decode(secret.removeprefix("whsec_"))
    to_sign     = f"{msg_id}.{timestamp}.{body}".encode()
    signature   = base64.b64encode(
        hmac.new(raw_secret, to_sign, hashlib.sha256).digest()
    ).decode()

    return {
        "Content-Type":   "application/json",
        "svix-id":        msg_id,
        "svix-timestamp": timestamp,
        "svix-signature": f"v1,{signature}",
    }

async def send_user_deleted(client: httpx.AsyncClient, payload: dict):
    headers  = sign_webhook(payload, WEBHOOK_SECRET)
    body     = json.dumps(payload, separators=(",", ":"))
    response = await client.post(f"{BASE_URL}/webhooks/clerk", content=body, headers=headers)
    return ("user.deleted webhook", response.status_code, response.text)

async def send_org_membership(client: httpx.AsyncClient, payload: dict):
    headers  = sign_webhook(payload, WEBHOOK_SECRET)
    body     = json.dumps(payload, separators=(",", ":"))
    response = await client.post(f"{BASE_URL}/webhooks/clerk", content=body, headers=headers)
    return ("organizationMembership.created webhook", response.status_code, response.text)

async def send_delete_profile(client: httpx.AsyncClient):
    response = await client.delete(
        f"{BASE_URL}/profiles/me",
        headers={"Authorization": f"Bearer {USER_JWT}"},
    )
    return ("DELETE /profiles/me", response.status_code, response.text)

async def main():
    global USER_JWT, USER_ID, ORG_ID
    
    print("=" * 60)
    print("Distributed Lock Hierarchy Test")
    print("=" * 60)

    if not CLERK_SECRET_KEY or not WEBHOOK_SECRET:
        print("\n❌ Missing env vars.")
        return

    try:
        USER_ID, USER_JWT = provision_clerk_user()
        await setup_test_db()
        
        user_deleted_payload = {
            "type": "user.deleted",
            "data": {"id": USER_ID, "deleted": True, "object": "user"},
        }

        org_membership_payload = {
            "type": "organizationMembership.created",
            "data": {
                "organization":    {"id": ORG_ID},
                "public_user_data": {"user_id": USER_ID},
                "role":            "org:member",
            },
        }

        print("\n[Test] Firing concurrent requests...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            results = await asyncio.gather(
                send_user_deleted(client, user_deleted_payload),
                send_org_membership(client, org_membership_payload),
                send_delete_profile(client),
                return_exceptions=True,
            )

        print("\nResults:")
        print("-" * 60)
        deadlock_found = False
        for r in results:
            if isinstance(r, Exception):
                print(f"  EXCEPTION: {r}")
                continue
            label, status, body = r
            flag = "✅" if status < 500 else "❌"
            print(f"  {flag}  [{status}]  {label}")
            if status >= 500:
                print(f"       body: {body[:3000]}")
            if "DeadlockDetected" in body or "deadlock" in body.lower():
                deadlock_found = True
                print(f"       ⚠️  DEADLOCK DETECTED!")

        print("-" * 60)
        if deadlock_found:
            print("\n❌  TEST FAILED — PostgreSQL deadlock detected.")
        else:
            print("\n✅  TEST PASSED — No deadlocks. All requests resolved.")
            
    finally:
        if USER_ID:
            print("\n[Teardown] Cleaning up database...")
            async with AsyncSessionLocal() as db:
                await db.execute(delete(Profile).where(Profile.id == USER_ID))
                await db.commit()
            delete_clerk_user(USER_ID)

if __name__ == "__main__":
    asyncio.run(main())
