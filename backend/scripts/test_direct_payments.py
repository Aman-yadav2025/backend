"""
Direct Payment (Deal Purchase) – Fully Automated E2E Test
==========================================================
Tests the complete DIRECT payment webhook lifecycle:
  1. Recycler creates a listing
  2. Brand creates a DIRECT purchase (→ AWAITING_PAYMENT)
  3. Simulate payment.failed webhook → purchase stays AWAITING_PAYMENT
  4. Simulate order.paid webhook    → purchase becomes CONFIRMED
  5. Attempt to cancel a CONFIRMED purchase → 400 expected

No manual args required. Provisions Clerk users, seeds the DB, runs all
steps, and tears everything down automatically.

Run with: python scripts/test_direct_payments.py
"""

import asyncio
import hashlib
import hmac
import json
import os
import sys
import uuid

import requests
from dotenv import dotenv_values
from sqlalchemy import delete

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import AsyncSessionLocal
from app.models import (
    Company,
    CompanyMember,
    CompanyType,
    MaterialListing,
    MaterialPurchase,
    MaterialType,
    MemberRole,
    MemberStatus,
    PackType,
    Profile,
    SystemRole,
)

# ── Config ────────────────────────────────────────────────────────────────────

env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
env = dotenv_values(env_path)

CLERK_SECRET_KEY = env.get("CLERK_SECRET_KEY", "")
CLERK_API_BASE   = "https://api.clerk.com/v1"
BASE_URL         = os.getenv("API_URL", "http://localhost:8000")
WEBHOOK_SECRET   = env.get("RAZORPAY_WEBHOOK_SECRET", "Plastic_ai_ek_chutiya_app_backend_testing")

# Globals populated in setup
BRAND_TOKEN         = ""
BRAND_COMPANY_ID    = ""
RECYCLER_TOKEN      = ""
RECYCLER_COMPANY_ID = ""


# ── Clerk helpers ─────────────────────────────────────────────────────────────

def provision_clerk_user(prefix: str = "test") -> tuple[str, str]:
    print(f"\n[Setup] Provisioning Clerk user ({prefix})...")
    headers = {"Authorization": f"Bearer {CLERK_SECRET_KEY}", "Content-Type": "application/json"}
    email    = f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    password = f"TestPass123!{uuid.uuid4().hex[:8]}"

    resp = requests.post(f"{CLERK_API_BASE}/users", headers=headers,
                         json={"email_address": [email], "password": password})
    if not resp.ok:
        print(f"❌ Failed to create Clerk user: {resp.text}")
        sys.exit(1)

    clerk_user_id = resp.json()["id"]
    print(f"  ✅ Created Clerk user: {clerk_user_id}")

    resp       = requests.post(f"{CLERK_API_BASE}/sessions", headers=headers, json={"user_id": clerk_user_id})
    session_id = resp.json()["id"]
    resp       = requests.post(f"{CLERK_API_BASE}/sessions/{session_id}/tokens/dev_token", headers=headers, json={})
    jwt        = resp.json()["jwt"]
    print(f"  ✅ Minted JWT.")
    return clerk_user_id, jwt


def delete_clerk_user(clerk_user_id: str) -> None:
    print(f"\n[Teardown] Deleting Clerk user {clerk_user_id}...")
    headers = {"Authorization": f"Bearer {CLERK_SECRET_KEY}"}
    resp = requests.delete(f"{CLERK_API_BASE}/users/{clerk_user_id}", headers=headers)
    if resp.ok:
        print("  ✅ User deleted.")
    else:
        print(f"  ❌ Failed to delete Clerk user: {resp.text}")


# ── Database helpers ──────────────────────────────────────────────────────────

async def setup_test_db(brand_user_id: str, recycler_user_id: str) -> tuple[str, str]:
    brand_company_id    = uuid.uuid4()
    recycler_company_id = uuid.uuid4()

    print("\n[Setup] Seeding profiles, companies, and memberships...")
    async with AsyncSessionLocal() as db:
        db.add_all([
            Profile(id=brand_user_id,    email=f"{brand_user_id}@test.com",    system_role=SystemRole.BRAND_ADMIN),
            Profile(id=recycler_user_id, email=f"{recycler_user_id}@test.com", system_role=SystemRole.RECYCLER),
        ])
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            print("  ⚠️  Profiles already exist (webhook beat us). Proceeding...")

        db.add_all([
            Company(
                id=brand_company_id, clerk_org_id=f"org_b_{uuid.uuid4().hex[:10]}",
                owner_id=brand_user_id, name="DP Test Brand Co",
                company_email="dp_brand@test.com", mobile_number="9999999999",
                gst_number="GSTB123", company_pan_number="PANB12345",
                factory_address="1 Brand St", state="Delhi", city="Delhi",
                pincode="110001", contact_person_name="Brand Owner",
                designation="Owner", material=MaterialType.PLASTIC,
                company_type=CompanyType.BRAND, pack=PackType.STARTER,
                tier=1, wallet_balance=5_000_000.00,
            ),
            Company(
                id=recycler_company_id, clerk_org_id=f"org_r_{uuid.uuid4().hex[:10]}",
                owner_id=recycler_user_id, name="DP Test Recycler Co",
                company_email="dp_recycler@test.com", mobile_number="8888888888",
                gst_number="GSTR123", company_pan_number="PANR12345",
                factory_address="2 Recycler St", state="Delhi", city="Delhi",
                pincode="110002", contact_person_name="Recycler Owner",
                designation="Owner", material=MaterialType.PLASTIC,
                company_type=CompanyType.RECYCLER, pack=PackType.STARTER,
                tier=1, wallet_balance=0.00,
            ),
        ])
        await db.commit()

        db.add_all([
            CompanyMember(company_id=brand_company_id,    profile_id=brand_user_id,
                          member_role=MemberRole.OWNER, status=MemberStatus.ACTIVE),
            CompanyMember(company_id=recycler_company_id, profile_id=recycler_user_id,
                          member_role=MemberRole.OWNER, status=MemberStatus.ACTIVE),
        ])
        await db.commit()

    return str(brand_company_id), str(recycler_company_id)


async def teardown_test_db(brand_uid: str, recycler_uid: str,
                           brand_cid: str, recycler_cid: str) -> None:
    print("\n[Teardown] Cleaning up database...")
    ids = [uuid.UUID(brand_cid), uuid.UUID(recycler_cid)]
    async with AsyncSessionLocal() as db:
        await db.execute(delete(MaterialPurchase).where(MaterialPurchase.brand_id.in_(ids)))
        await db.execute(delete(MaterialListing).where(MaterialListing.recycler_id.in_(ids)))
        await db.execute(delete(CompanyMember).where(CompanyMember.company_id.in_(ids)))
        await db.execute(delete(Company).where(Company.id.in_(ids)))
        await db.execute(delete(Profile).where(Profile.id.in_([brand_uid, recycler_uid])))
        await db.commit()
    print("  ✅ DB cleaned up.")


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def api(method: str, endpoint: str, token: str,
        data: dict | None = None, raw_body: bytes | None = None,
        extra_headers: dict | None = None) -> requests.Response:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    url = f"{BASE_URL}{endpoint}"
    if raw_body is not None:
        resp = requests.request(method, url, headers=headers, data=raw_body)
    else:
        resp = requests.request(method, url, headers=headers, json=data)
    return resp


def make_signed_webhook(payload: dict) -> tuple[bytes, str]:
    """Serialise payload and HMAC-sign it with the webhook secret."""
    raw = json.dumps(payload, separators=(",", ":")).encode()
    sig = hmac.new(WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return raw, sig


def post_webhook(payload: dict) -> requests.Response:
    raw, sig = make_signed_webhook(payload)
    headers  = {"x-razorpay-signature": sig, "Content-Type": "application/json"}
    return requests.post(f"{BASE_URL}/webhooks/razorpay", headers=headers, data=raw)


# ── Test logic ────────────────────────────────────────────────────────────────

def run_direct_payment_test() -> None:
    print("\n" + "=" * 58)
    print("  🚀  DIRECT PAYMENT E2E TEST")
    print("=" * 58)

    # ── Step 1: Recycler creates a listing ───────────────────────────────────
    print("\n── Step 1: Recycler creates a material listing ──")
    resp = api("POST", f"/companies/{RECYCLER_COMPANY_ID}/listings", RECYCLER_TOKEN, {
        "material_type": "PLASTIC",
        "category": "PET Bottles",
        "grade": "A-Grade",
        "price_per_unit": 50.00,
        "total_quantity": 500.00,
    })
    assert resp.status_code in (200, 201), f"Create listing failed: {resp.status_code} {resp.text}"
    listing_id = resp.json()["id"]
    print(f"  ✅ Listing created: {listing_id}")

    # ── Step 2: Brand creates a DIRECT purchase ───────────────────────────────
    print("\n── Step 2: Brand creates a DIRECT purchase ──")
    resp = api("POST", f"/companies/{BRAND_COMPANY_ID}/marketplace/{listing_id}/purchase",
               BRAND_TOKEN, {"quantity": "100.00", "payment_method": "DIRECT"})
    assert resp.status_code in (200, 201), f"Create purchase failed: {resp.status_code} {resp.text}"
    purchase     = resp.json()
    purchase_id  = purchase["id"]
    order_id     = purchase["razorpay_order_id"]
    print(f"  ✅ Purchase created: {purchase_id}")
    print(f"     Order ID:         {order_id}")
    print(f"     Status:           {purchase['purchase_status']}")
    assert purchase["purchase_status"] == "AWAITING_PAYMENT", \
        f"Expected AWAITING_PAYMENT, got {purchase['purchase_status']}"

    # ── Step 3: Simulate payment.failed webhook ───────────────────────────────
    print("\n── Step 3: Simulate payment.failed webhook ──")
    resp = post_webhook({
        "event": "payment.failed",
        "payload": {
            "payment": {
                "entity": {"id": "pay_failed_test", "order_id": order_id, "status": "failed"}
            },
            "order": {
                "entity": {"id": order_id, "status": "attempted", "notes": {"purpose": "deal_purchase"}}
            },
        },
    })
    print(f"  Webhook response: {resp.status_code} {resp.json()}")
    # payment.failed is routed through _handle_payment_failed — server returns 200 either way
    assert resp.status_code == 200, f"Unexpected webhook status: {resp.status_code}"

    # ── Step 4: Verify purchase is still AWAITING_PAYMENT ────────────────────
    print("\n── Step 4: Verify purchase still AWAITING_PAYMENT ──")
    resp = api("GET", f"/companies/{BRAND_COMPANY_ID}/marketplace/purchases", BRAND_TOKEN)
    if resp.status_code != 200:
        print(f"  ❌ GET purchases failed {resp.status_code}: {resp.text}")
    assert resp.status_code == 200, f"Get purchases failed: {resp.status_code}"
    purchases = resp.json()
    match = next((p for p in purchases if p["id"] == purchase_id), None)
    assert match is not None, "Purchase not found in list"
    assert match["purchase_status"] == "AWAITING_PAYMENT", \
        f"Expected AWAITING_PAYMENT after failure, got {match['purchase_status']}"
    print(f"  ✅ Purchase still AWAITING_PAYMENT (correctly unaffected by payment.failed)")

    # ── Step 5: Simulate order.paid webhook ───────────────────────────────────
    print("\n── Step 5: Simulate order.paid webhook ──")
    resp = post_webhook({
        "event": "order.paid",
        "payload": {
            "order": {
                "entity": {
                    "id": order_id,
                    "status": "paid",
                    "notes": {"purpose": "deal_purchase"},
                }
            },
            "payment": {
                "entity": {"id": "pay_success_test", "order_id": order_id, "status": "captured"}
            },
        },
    })
    print(f"  Webhook response: {resp.status_code} {resp.json()}")
    assert resp.status_code == 200, f"Unexpected webhook status: {resp.status_code}"
    assert resp.json().get("handled") is True, "Expected handled=True on order.paid"

    # ── Step 6: Verify purchase is now CONFIRMED ──────────────────────────────
    print("\n── Step 6: Verify purchase is now CONFIRMED ──")
    resp = api("GET", f"/companies/{BRAND_COMPANY_ID}/marketplace/purchases", BRAND_TOKEN)
    assert resp.status_code == 200
    purchases = resp.json()
    match = next((p for p in purchases if p["id"] == purchase_id), None)
    assert match is not None, "Purchase not found after confirmation"
    assert match["purchase_status"] == "CONFIRMED", \
        f"Expected CONFIRMED, got {match['purchase_status']}"
    print(f"  ✅ Purchase is CONFIRMED")

    # ── Step 7: Cancellation guard on CONFIRMED purchase ──────────────────────
    print("\n── Step 7: Cancel a CONFIRMED purchase → expect 400 ──")
    resp = api("POST", f"/companies/{BRAND_COMPANY_ID}/marketplace/purchases/{purchase_id}/cancel",
               BRAND_TOKEN)
    assert resp.status_code == 400, \
        f"Expected 400 cancellation rejection, got {resp.status_code}: {resp.text}"
    print(f"  ✅ Cancel correctly rejected (400) for a CONFIRMED purchase")

    print("\n🎉  ALL DIRECT PAYMENT TESTS PASSED! 🎉\n")


# ── Orchestrator ──────────────────────────────────────────────────────────────

async def main() -> None:
    if not CLERK_SECRET_KEY:
        print("❌ ERROR: CLERK_SECRET_KEY is missing from .env!")
        sys.exit(1)

    brand_uid, brand_jwt = provision_clerk_user("dp_brand")
    recyc_uid, recyc_jwt = provision_clerk_user("dp_recyc")
    b_cid = r_cid = None

    try:
        b_cid, r_cid = await setup_test_db(brand_uid, recyc_uid)

        global BRAND_TOKEN, RECYCLER_TOKEN, BRAND_COMPANY_ID, RECYCLER_COMPANY_ID
        BRAND_TOKEN         = brand_jwt
        RECYCLER_TOKEN      = recyc_jwt
        BRAND_COMPANY_ID    = b_cid
        RECYCLER_COMPANY_ID = r_cid

        run_direct_payment_test()
    finally:
        if b_cid and r_cid:
            try:
                await teardown_test_db(brand_uid, recyc_uid, b_cid, r_cid)
            except Exception as e:
                print(f"  ⚠️  DB teardown failed: {e}")
        for uid in (brand_uid, recyc_uid):
            try:
                delete_clerk_user(uid)
            except Exception:
                pass


if __name__ == "__main__":
    asyncio.run(main())
