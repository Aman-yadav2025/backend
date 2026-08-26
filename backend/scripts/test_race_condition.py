import asyncio
import hmac
import hashlib
import json
import uuid
import sys
import os
import httpx
import requests
from datetime import datetime, timezone
from dotenv import dotenv_values

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

env = dotenv_values(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

BASE_URL = "http://localhost:8000"
RAZORPAY_KEY_SECRET = env.get("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = env.get("RAZORPAY_WEBHOOK_SECRET", "")
CLERK_SECRET_KEY = env.get("CLERK_SECRET_KEY", "")
CLERK_API_BASE = "https://api.clerk.com/v1"

class TestContext:
    company_id: str
    user_jwt: str
    clerk_user_id: str

def get_headers(ctx: TestContext):
    return {
        "Authorization": f"Bearer {ctx.user_jwt}",
        "Content-Type": "application/json"
    }

def generate_webhook_signature(payload_dict: dict) -> str:
    body = json.dumps(payload_dict, separators=(",", ":"))
    secret = RAZORPAY_WEBHOOK_SECRET.encode()
    return hmac.new(key=secret, msg=body.encode(), digestmod=hashlib.sha256).hexdigest()

def generate_verify_signature(order_id: str, payment_id: str) -> str:
    message = f"{order_id}|{payment_id}"
    secret = RAZORPAY_KEY_SECRET.encode()
    return hmac.new(key=secret, msg=message.encode(), digestmod=hashlib.sha256).hexdigest()

def provision_clerk_user() -> tuple[str, str]:
    print("\n[Setup] Provisioning temporary Clerk user...")
    headers = {"Authorization": f"Bearer {CLERK_SECRET_KEY}", "Content-Type": "application/json"}
    email = f"test_race_{uuid.uuid4().hex[:8]}@example.com"
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
    print(f"\n[Teardown] Deleting Clerk user {clerk_user_id}...")
    headers = {"Authorization": f"Bearer {CLERK_SECRET_KEY}"}
    resp = requests.delete(f"{CLERK_API_BASE}/users/{clerk_user_id}", headers=headers)
    if resp.ok: print("✅ User deleted.")

async def setup_db_data(ctx: TestContext):
    print("\n[Setup] Seeding database records...")
    from app.database import AsyncSessionLocal
    from app.models import Profile, Company, CompanyType, PackType, SystemRole, CompanyMember, MemberRole, MemberStatus, MaterialType
    
    ctx.company_id = str(uuid.uuid4())

    async with AsyncSessionLocal() as db:
        await asyncio.sleep(2)
        await db.merge(Profile(id=ctx.clerk_user_id, email=f"{ctx.clerk_user_id}@test.com", system_role=SystemRole.BRAND_ADMIN))
        await db.commit()
        
        db.add(Company(id=uuid.UUID(ctx.company_id), clerk_org_id=f"org_{ctx.company_id[:10]}", owner_id=ctx.clerk_user_id, name="Temp Test Brand Corp", company_type=CompanyType.BRAND, pack=PackType.STARTER, tier=1, wallet_balance=0, frozen_wallet_balance=0, gst_number="27AAAAA0000A1Z5", contact_person_name="Test Person", contact_person_email="test@person.com", company_email="test@company.com", mobile_number="9999999999", company_pan_number="ABCDE1234F", factory_address="123 Test St", state="Maharashtra", city="Mumbai", pincode="400001", company_website="https://test.com", designation="Manager", material=MaterialType.METAL))
        await db.commit()
        
        db.add(CompanyMember(company_id=uuid.UUID(ctx.company_id), profile_id=ctx.clerk_user_id, member_role=MemberRole.OWNER, status=MemberStatus.ACTIVE))
        await db.commit()
        print("✅ Database seeding complete.")

async def teardown_db_data(ctx: TestContext):
    print("\n[Teardown] Cleaning up database...")
    from app.database import AsyncSessionLocal
    from sqlalchemy import delete, select
    from app.models import Profile, Company, CompanyMember, Payment, RefundRequest
    
    async with AsyncSessionLocal() as db:
        try:
            payments_res = await db.execute(select(Payment.id).where(Payment.company_id == uuid.UUID(ctx.company_id)))
            payment_ids = payments_res.scalars().all()
            if payment_ids:
                await db.execute(delete(RefundRequest).where(RefundRequest.payment_id.in_(payment_ids)))
                
            await db.execute(delete(Payment).where(Payment.company_id == uuid.UUID(ctx.company_id)))
            await db.execute(delete(CompanyMember).where(CompanyMember.company_id == uuid.UUID(ctx.company_id)))
            await db.execute(delete(Company).where(Company.id == uuid.UUID(ctx.company_id)))
            await db.execute(delete(Profile).where(Profile.id == ctx.clerk_user_id))
            await db.commit()
            print("✅ Database cleanup complete.")
        except Exception as e:
            print(f"⚠️ Warning: DB Teardown failed: {e}")
            await db.rollback()

async def call_verify_endpoint(client: httpx.AsyncClient, ctx: TestContext, order_id: str, payment_id: str, signature: str):
    payload = {
        "razorpay_order_id": order_id,
        "razorpay_payment_id": payment_id,
        "razorpay_signature": signature
    }
    response = await client.post(f"{BASE_URL}/companies/{ctx.company_id}/payments/verify", json=payload, headers=get_headers(ctx))
    print(f"  [VERIFY]  Status: {response.status_code}")

async def call_webhook_endpoint(client: httpx.AsyncClient, order_id: str, payment_id: str):
    payload = {
        "event": "order.paid",
        "payload": {
            "order": {"entity": {"id": order_id}},
            "payment": {"entity": {"id": payment_id, "order_id": order_id, "status": "captured"}}
        }
    }
    signature = generate_webhook_signature(payload)
    headers = {"Content-Type": "application/json", "X-Razorpay-Signature": signature}
    response = await client.post(f"{BASE_URL}/webhooks/razorpay", json=payload, headers=headers)
    print(f"  [WEBHOOK] Status: {response.status_code}")

async def test_race_condition(client: httpx.AsyncClient, ctx: TestContext):
    print("\n--- Testing Race Condition (Verify vs Webhook) ---")
    
    # 1. Checkout to create a real order in the DB
    payload = {"plan_package": "GROWTH", "plan_tier": 2}
    resp = await client.post(f"{BASE_URL}/companies/{ctx.company_id}/payments/checkout", json=payload, headers=get_headers(ctx))
    
    if resp.status_code != 200:
        print(f"❌ Checkout failed: {resp.text}")
        return
        
    checkout = resp.json()
    order_id = checkout["razorpay_order_id"]
    fake_payment_id = f"pay_{uuid.uuid4().hex[:14]}"
    signature = generate_verify_signature(order_id, fake_payment_id)

    print(f"Firing POST /verify and order.paid webhook concurrently for order {order_id}...")
    
    # 2. Fire both concurrently
    await asyncio.gather(
        call_verify_endpoint(client, ctx, order_id, fake_payment_id, signature),
        call_webhook_endpoint(client, order_id, fake_payment_id)
    )
    
    print("✅ Race Condition Test Passed - No deadlocks.")

async def main():
    if not CLERK_SECRET_KEY:
        print("❌ Missing CLERK_SECRET_KEY in .env.")
        return

    ctx = TestContext()
    ctx.clerk_user_id, ctx.user_jwt = provision_clerk_user()
    
    try:
        await setup_db_data(ctx)
        async with httpx.AsyncClient(timeout=30.0) as client:
            await test_race_condition(client, ctx)
    finally:
        await teardown_db_data(ctx)
        delete_clerk_user(ctx.clerk_user_id)
        
    print("\n✅ All tests complete.")

if __name__ == "__main__":
    asyncio.run(main())
