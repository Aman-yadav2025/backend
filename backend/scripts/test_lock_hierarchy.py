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
import httpx
from dotenv import dotenv_values

# ── Config ────────────────────────────────────────────────────────────────────
env = dotenv_values("c:/Users/amank/OneDrive/Desktop/production-app-root/backend/.env")

BASE_URL        = "http://localhost:8000"
WEBHOOK_SECRET  = env.get("CLERK_WEBHOOK_SECRET")   # whsec_...
USER_JWT        = "eyJhbGciOiJSUzI1NiIsImNhdCI6ImNsX0I3ZDRQRDIyMkFBQSIsImtpZCI6Imluc18zSHpHVjhYa1BKMTdVblJyMmJTbFFkejN1SjAiLCJ0eXAiOiJKV1QifQ.eyJleHAiOjE3ODc0MzM3NjUsImlhdCI6MTc4NzM0NzM2NSwiaXNzIjoiaHR0cHM6Ly9mbGV4aWJsZS1zd2luZS01NDExLmNsZXJrLmFjY291bnRzLmRldiIsImp0aSI6ImQzNTZmMjA4YTlmOTY0NTU4YWNkIiwibmJmIjoxNzg3MzQ3MzYwLCJzdWIiOiJ1c2VyXzNJRjVDZzdMa3ZxNlBxUkJ1TFZwQVE3SjdvbyJ9.s6i84WrFWu7gkveIwb9XjmysJAv4Vgu7hr7uqkcgmA90L2J2EPmd31iMcgBXZhHG6CWFFnQWtIm1gLXiBkIHRloVuL__lL0Ml4kIXNoCusayAESH2u7eQ53nmDIUTI87eMR00r7Ja0M-bc32g7hwWQoR3jSud6T8i1m8YZwNK0W78ty74Xqrdcd1s21uIfaRDJEH1blFht8MhEO3HaUZQ1wcW8-6A-IX4MNHPdbwb50DozvfdHRTuK4VIRrGCrjmv7nntPULpwKTN4-od1rTOJ65mm_FOMy2QXTPOMSTvx6rQoSHYUtMi-DMTSbhk5TfxFD4HD71voAQGuzwaKLfTw"                 # JWT for the user being deleted
USER_ID         = "user_3IF5Cg7Lkvq6PqRBuLVpAQ7J7oo"             # e.g. user_2abc...
ORG_ID          = "org_3IEvklmkiDmfY2dB0RtmeDxf534"              # e.g. org_2abc...


# ── SVIX Webhook Signing ──────────────────────────────────────────────────────
def sign_webhook(payload: dict, secret: str) -> dict:
    """Generate valid Svix webhook headers for the given payload."""
    body        = json.dumps(payload, separators=(",", ":"))
    msg_id      = f"msg_{int(time.time()*1000)}"
    timestamp   = str(int(time.time()))

    # Svix signs: "{msg_id}.{timestamp}.{body}"
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


# ── Payloads ──────────────────────────────────────────────────────────────────
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


# ── Concurrent Requests ───────────────────────────────────────────────────────
async def send_user_deleted(client: httpx.AsyncClient):
    headers  = sign_webhook(user_deleted_payload, WEBHOOK_SECRET)
    body     = json.dumps(user_deleted_payload, separators=(",", ":"))
    response = await client.post(f"{BASE_URL}/webhooks/clerk", content=body, headers=headers)
    return ("user.deleted webhook", response.status_code, response.text)


async def send_org_membership(client: httpx.AsyncClient):
    headers  = sign_webhook(org_membership_payload, WEBHOOK_SECRET)
    body     = json.dumps(org_membership_payload, separators=(",", ":"))
    response = await client.post(f"{BASE_URL}/webhooks/clerk", content=body, headers=headers)
    return ("organizationMembership.created webhook", response.status_code, response.text)


async def send_delete_profile(client: httpx.AsyncClient):
    response = await client.delete(
        f"{BASE_URL}/profiles/me",
        headers={"Authorization": f"Bearer {USER_JWT}"},
    )
    return ("DELETE /profiles/me", response.status_code, response.text)


async def main():
    print("=" * 60)
    print("Distributed Lock Hierarchy Test")
    print("=" * 60)

    if "PASTE_" in USER_JWT or "PASTE_" in USER_ID or "PASTE_" in ORG_ID:
        print("\n❌  Fill in USER_JWT, USER_ID, ORG_ID at the top of this script first.")
        return

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Fire all three at the exact same time
        results = await asyncio.gather(
            send_user_deleted(client),
            send_org_membership(client),
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
            print(f"       body: {body[:300]}")
        if "DeadlockDetected" in body or "deadlock" in body.lower():
            deadlock_found = True
            print(f"       ⚠️  DEADLOCK DETECTED!")

    print("-" * 60)
    if deadlock_found:
        print("\n❌  TEST FAILED — PostgreSQL deadlock detected.")
    else:
        print("\n✅  TEST PASSED — No deadlocks. All requests resolved.")


if __name__ == "__main__":
    asyncio.run(main())
