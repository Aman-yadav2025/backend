import asyncio
import hmac
import hashlib
import json
import uuid
import sys
import os
from datetime import datetime, timedelta, timezone

# Add the backend root directory to Python's path so it can find the 'app' module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
import requests
from dotenv import dotenv_values

# Load env variables explicitly so we can generate signatures
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
    """Creates a temporary Clerk user and mints a session JWT for them."""
    print("\n[Setup] Provisioning temporary Clerk user...")
    headers = {"Authorization": f"Bearer {CLERK_SECRET_KEY}", "Content-Type": "application/json"}
    
    # 1. Create User
    email = f"test_payments_{uuid.uuid4().hex[:8]}@example.com"
    password = f"TestPass123!{uuid.uuid4().hex[:8]}"
    resp = requests.post(f"{CLERK_API_BASE}/users", headers=headers, json={"email_address": [email], "password": password})
    if not resp.ok:
        print(f"❌ Failed to create Clerk user: {resp.text}")
        sys.exit(1)
    
    clerk_user_id = resp.json()["id"]
    print(f"✅ Created Clerk User: {clerk_user_id}")

    # 2. Create Session
    resp = requests.post(f"{CLERK_API_BASE}/sessions", headers=headers, json={"user_id": clerk_user_id})
    if not resp.ok:
        print(f"❌ Failed to create session: {resp.text}")
        sys.exit(1)
    session_id = resp.json()["id"]

    # 3. Create Session Token (JWT)
    resp = requests.post(f"{CLERK_API_BASE}/sessions/{session_id}/tokens/dev_token", headers=headers, json={})
    if not resp.ok:
        print(f"❌ Failed to create token: {resp.text}")
        sys.exit(1)
    
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
        print(f"⚠️ Failed to delete user: {resp.text}")

async def setup_db_data(ctx: TestContext):
    """Seed the database with the Profile, Company, Member and Promo codes."""
    print("\n[Setup] Seeding database records...")
    import asyncio
    from app.database import AsyncSessionLocal
    from app.models import Profile, Company, CompanyType, PackType, SystemRole, PromoCode, DiscountType, CompanyMember, MemberRole, MemberStatus, MaterialType
    from sqlalchemy import delete, select
    
    ctx.company_id = str(uuid.uuid4())
    other_company_id = str(uuid.uuid4())
    other_profile_id = str(uuid.uuid4())
    
    ctx.other_company_id = other_company_id
    ctx.other_profile_id = other_profile_id
    
    now = datetime.now(timezone.utc)
    
    promos = {
        "EXPIRED_PROMO": PromoCode(code="EXPIRED_PROMO", discount_type=DiscountType.FIXED_AMOUNT, discount_value=100, max_uses=10, current_uses=0, valid_from=now - timedelta(days=10), valid_until=now - timedelta(days=1), is_active=True),
        "INACTIVE_PROMO": PromoCode(code="INACTIVE_PROMO", discount_type=DiscountType.FIXED_AMOUNT, discount_value=100, max_uses=10, current_uses=0, valid_from=now - timedelta(days=10), valid_until=now + timedelta(days=10), is_active=False),
        "WRONG_ORG_PROMO": PromoCode(code="WRONG_ORG_PROMO", discount_type=DiscountType.FIXED_AMOUNT, discount_value=100, max_uses=10, current_uses=0, valid_from=now - timedelta(days=10), valid_until=now + timedelta(days=10), is_active=True, assigned_company_id=uuid.UUID(other_company_id)),
        "FREE_PROMO": PromoCode(code="FREE_PROMO", discount_type=DiscountType.PERCENTAGE, discount_value=100, max_uses=10, current_uses=0, valid_from=now - timedelta(days=10), valid_until=now + timedelta(days=10), is_active=True),
        "FIXED_PROMO": PromoCode(code="FIXED_PROMO", discount_type=DiscountType.FIXED_AMOUNT, discount_value=100, max_uses=10, current_uses=0, valid_from=now - timedelta(days=10), valid_until=now + timedelta(days=10), is_active=True),
    }

    async with AsyncSessionLocal() as db:
        # Give webhooks time to finish processing if necessary
        await asyncio.sleep(2)
        
        # Create Profiles using merge to handle race conditions with Clerk Webhooks
        await db.merge(Profile(id=ctx.clerk_user_id, email=f"{ctx.clerk_user_id}@test.com", system_role=SystemRole.BRAND_ADMIN))
        await db.merge(Profile(id=other_profile_id, email=f"{other_profile_id}@test.com", system_role=SystemRole.BRAND_ADMIN))
        await db.commit()
        
        # Create Company (Brand required for wallet recharges)
        db.add(Company(id=uuid.UUID(ctx.company_id), clerk_org_id=f"org_{ctx.company_id[:10]}", owner_id=ctx.clerk_user_id, name="Temp Test Brand Corp", company_type=CompanyType.BRAND, pack=PackType.STARTER, tier=1, wallet_balance=0, frozen_wallet_balance=0, gst_number="27AAAAA0000A1Z5", contact_person_name="Test Person", contact_person_email="test@person.com", company_email="test@company.com", mobile_number="9999999999", company_pan_number="ABCDE1234F", factory_address="123 Test St", state="Maharashtra", city="Mumbai", pincode="400001", company_website="https://test.com", designation="Manager", material=MaterialType.METAL))
        # Create Another Company (For the WRONG_ORG_PROMO foreign key)
        db.add(Company(id=uuid.UUID(other_company_id), clerk_org_id=f"org_{str(other_company_id)[:10]}", owner_id=other_profile_id, name="Other Brand Corp", company_type=CompanyType.BRAND, pack=PackType.STARTER, tier=1, wallet_balance=0, frozen_wallet_balance=0, gst_number="27AAAAA0000A1Z5", contact_person_name="Test Person", contact_person_email="test@person.com", company_email="test@company.com", mobile_number="9999999999", company_pan_number="ABCDE1234F", factory_address="123 Test St", state="Maharashtra", city="Mumbai", pincode="400001", company_website="https://test.com", designation="Manager", material=MaterialType.METAL))
        await db.commit()
        
        # Create Membership
        db.add(CompanyMember(company_id=uuid.UUID(ctx.company_id), profile_id=ctx.clerk_user_id, member_role=MemberRole.OWNER, status=MemberStatus.ACTIVE))
        await db.commit()

        # Insert Promos
        for code in promos.values():
            await db.execute(delete(PromoCode).where(PromoCode.code == code.code))
            db.add(code)
        await db.commit()
        print("✅ Database seeding complete.")


async def teardown_db_data(ctx: TestContext):
    """Clean up all the generated test data from the database."""
    print("\n[Teardown] Cleaning up database...")
    from app.database import AsyncSessionLocal
    from sqlalchemy import delete, select
    from app.models import (
        Profile, Company, CompanyMember, PromoCode, Payment, 
        WalletRecharge, RefundRequest
    )
    
    async with AsyncSessionLocal() as db:
        try:
            # 1. Gather payments to delete refunds first
            payments_res = await db.execute(select(Payment.id).where(Payment.company_id == uuid.UUID(ctx.company_id)))
            payment_ids = payments_res.scalars().all()
            if payment_ids:
                await db.execute(delete(RefundRequest).where(RefundRequest.payment_id.in_(payment_ids)))
                
            # 2. Clean up transactions
            await db.execute(delete(Payment).where(Payment.company_id == uuid.UUID(ctx.company_id)))
            await db.execute(delete(WalletRecharge).where(WalletRecharge.company_id == uuid.UUID(ctx.company_id)))
            
            # 3. Clean up members, companies, profiles
            await db.execute(delete(CompanyMember).where(CompanyMember.company_id == uuid.UUID(ctx.company_id)))
            await db.execute(delete(Company).where(Company.id == uuid.UUID(ctx.company_id)))
            
            if hasattr(ctx, "other_company_id"):
                await db.execute(delete(Company).where(Company.id == uuid.UUID(ctx.other_company_id)))
                
            await db.execute(delete(Profile).where(Profile.id.in_([ctx.clerk_user_id, getattr(ctx, "other_profile_id", "")])))
            
            # 4. Clean up promos
            await db.execute(delete(PromoCode).where(PromoCode.code.in_(["EXPIRED_PROMO", "INACTIVE_PROMO", "WRONG_ORG_PROMO", "FREE_PROMO", "FIXED_PROMO"])))
            
            await db.commit()
            print("✅ Database cleanup complete.")
        except Exception as e:
            print(f"⚠️ Warning: DB Teardown failed: {e}")
            await db.rollback()

async def test_promo_code_failures(client: httpx.AsyncClient, ctx: TestContext):
    print("\n--- Testing Promo Code Expiration & State ---")
    failures = ["EXPIRED_PROMO", "INACTIVE_PROMO", "WRONG_ORG_PROMO"]
    for code in failures:
        payload = {"promo_code": code, "plan_package": "GROWTH", "plan_tier": 1}
        resp = await client.post(f"{BASE_URL}/companies/{ctx.company_id}/payments/checkout", json=payload, headers=get_headers(ctx))
        if resp.status_code == 400:
            print(f"✅ {code} rejected correctly (400): {resp.json()['detail']}")
        else:
            print(f"❌ {code} failed! Expected 400, got {resp.status_code}")

async def test_free_order_skip(client: httpx.AsyncClient, ctx: TestContext):
    print("\n--- Testing Free Order Skip ---")
    payload = {"promo_code": "FREE_PROMO", "plan_package": "GROWTH", "plan_tier": 1}
    resp = await client.post(f"{BASE_URL}/companies/{ctx.company_id}/payments/checkout", json=payload, headers=get_headers(ctx))
    if resp.status_code == 200:
        data = resp.json()
        if float(data["amount_paid"]) == 0.0 and data["razorpay_key_id"] == "free":
            print("✅ 100% discount order instantly succeeded and bypassed Razorpay.")
        else:
            print(f"❌ Order succeeded but amount_paid is {data['amount_paid']}, expected 0.")
    else:
        print(f"❌ Free order skip failed with {resp.status_code}: {resp.text}")

async def test_race_condition(client: httpx.AsyncClient, ctx: TestContext) -> dict:
    print("\n--- Testing Race Condition (Verify vs Webhook) ---")
    payload = {"plan_package": "GROWTH", "plan_tier": 1}
    resp = await client.post(f"{BASE_URL}/companies/{ctx.company_id}/payments/checkout", json=payload, headers=get_headers(ctx))
    if resp.status_code != 200:
        print(f"❌ Checkout failed: {resp.text}")
        return None
        
    order = resp.json()
    order_id = order["razorpay_order_id"]
    fake_payment_id = f"pay_{uuid.uuid4().hex[:14]}"
    
    verify_sig = generate_verify_signature(order_id, fake_payment_id)
    verify_payload = {"razorpay_order_id": order_id, "razorpay_payment_id": fake_payment_id, "razorpay_signature": verify_sig}
    
    webhook_payload = {"event": "order.paid", "payload": {"order": {"entity": {"id": order_id}}, "payment": {"entity": {"id": fake_payment_id}}}}
    webhook_headers = {"x-razorpay-signature": generate_webhook_signature(webhook_payload), "Content-Type": "application/json"}
    
    print(f"Firing POST /verify and order.paid webhook concurrently for order {order_id}...")
    
    async def send_verify():
        r = await client.post(f"{BASE_URL}/companies/{ctx.company_id}/payments/verify", json=verify_payload, headers=get_headers(ctx))
        return ("POST /verify", r.status_code, r.text)

    async def send_webhook():
        r = await client.post(f"{BASE_URL}/webhooks/razorpay", json=webhook_payload, headers=webhook_headers)
        return ("order.paid webhook", r.status_code, r.text)

    results = await asyncio.gather(send_verify(), send_webhook(), return_exceptions=True)
    deadlock = False
    for r in results:
        if isinstance(r, Exception):
            print(f"  EXCEPTION: {r}")
            continue
        label, status, body = r
        flag = "✅" if status < 500 else "❌"
        print(f"  {flag}  [{status}]  {label}")
        if "DeadlockDetected" in body or "deadlock" in body.lower():
            deadlock = True

    if not deadlock:
        print("✅ Race Condition Test Passed - No deadlocks.")
    else:
        print("❌ DEADLOCK DETECTED!")
    return order

async def test_failed_payment_promo_release(client: httpx.AsyncClient, ctx: TestContext):
    print("\n--- Testing Failed Payment Promo Release ---")
    
    # Sleep briefly to avoid triggering rate limit after the burst of race condition tests
    await asyncio.sleep(2)
    
    payload = {"promo_code": "FIXED_PROMO", "plan_package": "GROWTH", "plan_tier": 1}
    resp = await client.post(f"{BASE_URL}/companies/{ctx.company_id}/payments/checkout", json=payload, headers=get_headers(ctx))
    if resp.status_code != 200:
        print(f"❌ Checkout failed: {resp.text}")
        return
        
    order = resp.json()
    order_id = order["razorpay_order_id"]
    fake_payment_id = f"pay_{uuid.uuid4().hex[:14]}"
    
    webhook_payload = {"event": "payment.failed", "payload": {"payment": {"entity": {"id": fake_payment_id, "order_id": order_id}}}}
    webhook_headers = {"x-razorpay-signature": generate_webhook_signature(webhook_payload), "Content-Type": "application/json"}
    w_resp = await client.post(f"{BASE_URL}/webhooks/razorpay", json=webhook_payload, headers=webhook_headers)
    
    if w_resp.status_code == 200:
        print("✅ payment.failed webhook processed. Promo slot should be freed.")
    else:
        print(f"❌ Webhook failed: {w_resp.status_code} {w_resp.text}")

async def test_over_refund_request(client: httpx.AsyncClient, ctx: TestContext, successful_order: dict):
    print("\n--- Testing Over-Refund Request Limit ---")
    if not successful_order:
        print("⏭️ Skipping (needs successful order)")
        return
        
    payment_id = successful_order["payment_id"]
    amount_paid = float(successful_order["amount_paid"])
    
    amount_1 = round(amount_paid * 0.8, 2)
    resp1 = await client.post(f"{BASE_URL}/companies/{ctx.company_id}/payments/{payment_id}/refund-request", json={"amount": amount_1}, headers=get_headers(ctx))
    if resp1.status_code == 201:
        print(f"✅ First refund request for {amount_1} succeeded.")
    else:
        print(f"❌ First refund request failed: {resp1.text}")
        return
        
    amount_2 = round(amount_paid * 0.3, 2)
    resp2 = await client.post(f"{BASE_URL}/companies/{ctx.company_id}/payments/{payment_id}/refund-request", json={"amount": amount_2}, headers=get_headers(ctx))
    if resp2.status_code == 400:
        print(f"✅ Second refund request for {amount_2} correctly rejected (400): {resp2.json()['detail']}")
    else:
        print(f"❌ Second refund request failed validation! Expected 400, got {resp2.status_code}")

async def test_wallet_recharge(client: httpx.AsyncClient, ctx: TestContext):
    print("\n--- Testing Wallet Recharge (Checkout -> Webhook) ---")
    
    # 1. Checkout
    payload = {"amount": 5000}
    resp = await client.post(f"{BASE_URL}/companies/{ctx.company_id}/wallet/recharge/checkout", json=payload, headers=get_headers(ctx))
    
    if resp.status_code != 200:
        print(f"❌ Wallet Recharge Checkout failed: {resp.status_code} {resp.text}")
        return
    
    recharge = resp.json()
    order_id = recharge["razorpay_order_id"]
    fake_payment_id = f"pay_{uuid.uuid4().hex[:14]}"
    
    print(f"✅ Created recharge order: {order_id}")
    
    # 2. Verify endpoint (to test idempotency with webhook)
    verify_sig = generate_verify_signature(order_id, fake_payment_id)
    verify_payload = {"razorpay_order_id": order_id, "razorpay_payment_id": fake_payment_id, "razorpay_signature": verify_sig}
    v_resp = await client.post(f"{BASE_URL}/companies/{ctx.company_id}/wallet/recharge/verify", json=verify_payload, headers=get_headers(ctx))
    if v_resp.status_code == 200:
        print(f"✅ Wallet Recharge Verify successful.")
    else:
        print(f"❌ Verify failed: {v_resp.status_code} {v_resp.text}")

    # 3. Simulate Webhook order.paid
    webhook_payload = {
        "event": "order.paid", 
        "payload": {
            "order": {"entity": {"id": order_id, "notes": {"purpose": "wallet_recharge"}}}, 
            "payment": {"entity": {"id": fake_payment_id}}
        }
    }
    webhook_headers = {"x-razorpay-signature": generate_webhook_signature(webhook_payload), "Content-Type": "application/json"}
    w_resp = await client.post(f"{BASE_URL}/webhooks/razorpay", json=webhook_payload, headers=webhook_headers)
    
    if w_resp.status_code == 200:
        print("✅ Wallet Recharge Webhook handled successfully (idempotent).")
    else:
        print(f"❌ Wallet Recharge Webhook failed: {w_resp.status_code} {w_resp.text}")
        
    # 4. Check Wallet Balance
    b_resp = await client.get(f"{BASE_URL}/companies/{ctx.company_id}/wallet", headers=get_headers(ctx))
    if b_resp.status_code == 200:
        balance = b_resp.json().get("wallet_balance")
        if float(balance) == 5000.0:
             print(f"✅ Wallet Balance accurately reflected: {balance}")
        else:
             print(f"❌ Wallet Balance is {balance}, expected 5000.0")
    else:
        print(f"❌ Failed to fetch wallet balance: {b_resp.status_code} {b_resp.text}")


async def test_wallet_recharge_failed(client: httpx.AsyncClient, ctx: TestContext):
    print("\n--- Testing Wallet Recharge Failed Webhook ---")
    
    # 1. Checkout
    payload = {"amount": 2000}
    resp = await client.post(f"{BASE_URL}/companies/{ctx.company_id}/wallet/recharge/checkout", json=payload, headers=get_headers(ctx))
    if resp.status_code != 200:
        print(f"❌ Wallet Recharge Checkout failed: {resp.text}")
        return
        
    recharge = resp.json()
    order_id = recharge["razorpay_order_id"]
    fake_payment_id = f"pay_{uuid.uuid4().hex[:14]}"
    
    # 2. Fire payment.failed webhook
    webhook_payload = {"event": "payment.failed", "payload": {"payment": {"entity": {"id": fake_payment_id, "order_id": order_id}}}}
    webhook_headers = {"x-razorpay-signature": generate_webhook_signature(webhook_payload), "Content-Type": "application/json"}
    w_resp = await client.post(f"{BASE_URL}/webhooks/razorpay", json=webhook_payload, headers=webhook_headers)
    
    if w_resp.status_code == 200:
        print("✅ payment.failed webhook for wallet recharge processed.")
    else:
        print(f"❌ Webhook failed: {w_resp.status_code} {w_resp.text}")

async def main():
    if not CLERK_SECRET_KEY:
        print("❌ Missing CLERK_SECRET_KEY in .env. Cannot provision test user dynamically.")
        return

    ctx = TestContext()
    ctx.clerk_user_id, ctx.user_jwt = provision_clerk_user()
    
    try:
        await setup_db_data(ctx)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            await test_promo_code_failures(client, ctx)
            await test_free_order_skip(client, ctx)
            successful_order = await test_race_condition(client, ctx)
            await test_failed_payment_promo_release(client, ctx)
            await test_over_refund_request(client, ctx, successful_order)
            
            await test_wallet_recharge(client, ctx)
            await test_wallet_recharge_failed(client, ctx)
            
    finally:
        await teardown_db_data(ctx)
        delete_clerk_user(ctx.clerk_user_id)
        
    print("\n✅ All tests complete.")

if __name__ == "__main__":
    asyncio.run(main())
