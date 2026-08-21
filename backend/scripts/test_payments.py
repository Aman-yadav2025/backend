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
from dotenv import dotenv_values

# Load env variables explicitly so we can generate signatures
env = dotenv_values("c:/Users/amank/OneDrive/Desktop/production-app-root/backend/.env")

# --- IMPORTANT ---
# Fill these in before running!
BASE_URL = "http://localhost:8000"
COMPANY_ID = "439df42d-0452-49d4-992a-efceaff520d5"      # e.g., "123e4567-e89b-12d3-a456-426614174000"
USER_JWT = "eyJhbGciOiJSUzI1NiIsImNhdCI6ImNsX0I3ZDRQRDIyMkFBQSIsImtpZCI6Imluc18zSHpHVjhYa1BKMTdVblJyMmJTbFFkejN1SjAiLCJ0eXAiOiJKV1QifQ.eyJleHAiOjE3ODc0MzY0MTEsImlhdCI6MTc4NzM1MDAxMSwiaXNzIjoiaHR0cHM6Ly9mbGV4aWJsZS1zd2luZS01NDExLmNsZXJrLmFjY291bnRzLmRldiIsImp0aSI6IjNlOTVlMDA4NGIzOTc4YjI1OTlkIiwibmJmIjoxNzg3MzUwMDA2LCJzdWIiOiJ1c2VyXzNJRkFYalJUQ0VxQkpDUFFDRUZOUmk2azVXVCJ9.PlzWpNmljARwcXAVe5I37Su1tdmpKVtnHOVxAGmE7xyC_d12PpHZogeUE202EB-dJruxApCjOkLMpZHDWTx6pUcqbIPQ0hGg5w__D7CvxxVrlcbhMiKeF0Aat7jR_uXhYT6SVW2kWd-gWgFrHa3OmoFs2gMV66dHzra_0d9_y7kDdJjduKaRhQ5zcBUICg0dX-w3i-vz5hKqvZGkWpLluaypEcU67iUfRqX-ZEBN9b5NSoOoPZsGHsh_Gv_JaGkUHPffabF8YM-KRQKQIqa84F63fqHExl3pDtliQFiD6B1bmItX0blBWnf61cvozTFfDiQf0kHBF9IsudZpX9JhVw"         # Company owner/admin JWT
RAZORPAY_KEY_SECRET = env.get("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = env.get("RAZORPAY_WEBHOOK_SECRET", "")
# -----------------

def get_headers():
    return {
        "Authorization": f"Bearer {USER_JWT}",
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

async def setup_promo_codes():
    """Seed the database directly with test promo codes bypassing the platform admin requirement."""
    print("\n[Setup] Seeding promo codes in the database...")
    from app.database import AsyncSessionLocal
    from app.models import PromoCode, DiscountType, Profile, Company, SystemRole, CompanyType, PackType
    
    cid = uuid.UUID(COMPANY_ID)
    now = datetime.now(timezone.utc)
    
    dummy_company_id = uuid.uuid4()
    dummy_profile_id = f"dummy_{dummy_company_id.hex[:10]}"
    
    promos = {
        "EXPIRED_PROMO": PromoCode(
            code="EXPIRED_PROMO", discount_type=DiscountType.FIXED_AMOUNT, discount_value=100, max_uses=10, current_uses=0,
            valid_from=now - timedelta(days=10), valid_until=now - timedelta(days=1), is_active=True
        ),
        "INACTIVE_PROMO": PromoCode(
            code="INACTIVE_PROMO", discount_type=DiscountType.FIXED_AMOUNT, discount_value=100, max_uses=10, current_uses=0,
            valid_from=now - timedelta(days=10), valid_until=now + timedelta(days=10), is_active=False
        ),
        "WRONG_ORG_PROMO": PromoCode(
            code="WRONG_ORG_PROMO", discount_type=DiscountType.FIXED_AMOUNT, discount_value=100, max_uses=10, current_uses=0,
            valid_from=now - timedelta(days=10), valid_until=now + timedelta(days=10), is_active=True,
            assigned_company_id=dummy_company_id # Valid dummy company
        ),
        "FREE_PROMO": PromoCode(
            code="FREE_PROMO", discount_type=DiscountType.PERCENTAGE, discount_value=100, max_uses=10, current_uses=0,
            valid_from=now - timedelta(days=10), valid_until=now + timedelta(days=10), is_active=True
        ),
        "FIXED_PROMO": PromoCode(
            code="FIXED_PROMO", discount_type=DiscountType.FIXED_AMOUNT, discount_value=100, max_uses=10, current_uses=0,
            valid_from=now - timedelta(days=10), valid_until=now + timedelta(days=10), is_active=True
        ),
    }
    
    async with AsyncSessionLocal() as db:
        # Insert dummy Profile FIRST and commit it
        db.add(Profile(
            id=dummy_profile_id,
            email=f"{dummy_profile_id}@test.com",
            system_role=SystemRole.BRAND_ADMIN
        ))
        await db.commit()
        
        # Then insert Company and commit it
        db.add(Company(
            id=dummy_company_id,
            clerk_org_id=f"org_{dummy_company_id.hex[:10]}",
            owner_id=dummy_profile_id,
            name="Dummy Corp",
            company_type=CompanyType.BRAND,
            pack=PackType.STARTER,
            tier=1
        ))
        await db.commit()
        
        # Now insert the promos
        for code in promos.values():
            from sqlalchemy import delete
            await db.execute(delete(PromoCode).where(PromoCode.code == code.code))
            db.add(code)
        await db.commit()
    print("[Setup] Promo codes ready.")

async def test_promo_code_failures(client: httpx.AsyncClient):
    print("\n--- Testing Promo Code Expiration & State ---")
    failures = ["EXPIRED_PROMO", "INACTIVE_PROMO", "WRONG_ORG_PROMO"]
    for code in failures:
        payload = {"promo_code": code, "plan_package": "GROWTH", "plan_tier": 1}
        resp = await client.post(f"{BASE_URL}/companies/{COMPANY_ID}/payments/checkout", json=payload, headers=get_headers())
        if resp.status_code == 400:
            print(f"✅ {code} rejected correctly (400): {resp.json()['detail']}")
        else:
            print(f"❌ {code} failed! Expected 400, got {resp.status_code}")

async def test_free_order_skip(client: httpx.AsyncClient):
    print("\n--- Testing Free Order Skip ---")
    payload = {"promo_code": "FREE_PROMO", "plan_package": "GROWTH", "plan_tier": 1}
    resp = await client.post(f"{BASE_URL}/companies/{COMPANY_ID}/payments/checkout", json=payload, headers=get_headers())
    
    if resp.status_code == 200:
        data = resp.json()
        if float(data["amount_paid"]) == 0.0 and data["razorpay_key_id"] == "free":
            print("✅ 100% discount order instantly succeeded and bypassed Razorpay.")
        else:
            print(f"❌ Order succeeded but amount_paid is {data['amount_paid']}, expected 0.")
    else:
        print(f"❌ Free order skip failed with {resp.status_code}: {resp.text}")

async def test_race_condition(client: httpx.AsyncClient) -> dict:
    print("\n--- Testing Race Condition (Verify vs Webhook) ---")
    # 1. Create a regular checkout order
    payload = {"plan_package": "GROWTH", "plan_tier": 1}
    resp = await client.post(f"{BASE_URL}/companies/{COMPANY_ID}/payments/checkout", json=payload, headers=get_headers())
    
    if resp.status_code != 200:
        print(f"❌ Checkout failed: {resp.text}")
        return None
        
    order = resp.json()
    order_id = order["razorpay_order_id"]
    fake_payment_id = f"pay_{uuid.uuid4().hex[:14]}"
    
    # 2. Build the Verify Request
    verify_sig = generate_verify_signature(order_id, fake_payment_id)
    verify_payload = {
        "razorpay_order_id": order_id,
        "razorpay_payment_id": fake_payment_id,
        "razorpay_signature": verify_sig
    }
    
    # 3. Build the Webhook Request
    webhook_payload = {
        "event": "order.paid",
        "payload": {
            "order": {"entity": {"id": order_id}},
            "payment": {"entity": {"id": fake_payment_id}}
        }
    }
    webhook_sig = generate_webhook_signature(webhook_payload)
    webhook_headers = {"x-razorpay-signature": webhook_sig, "Content-Type": "application/json"}
    
    # 4. Fire BOTH at the exact same time
    print(f"Firing POST /verify and order.paid webhook concurrently for order {order_id}...")
    
    async def send_verify():
        r = await client.post(f"{BASE_URL}/companies/{COMPANY_ID}/payments/verify", json=verify_payload, headers=get_headers())
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

async def test_failed_payment_promo_release(client: httpx.AsyncClient):
    print("\n--- Testing Failed Payment Promo Release ---")
    
    # 1. Checkout using the fixed promo
    payload = {"promo_code": "FIXED_PROMO", "plan_package": "GROWTH", "plan_tier": 1}
    resp = await client.post(f"{BASE_URL}/companies/{COMPANY_ID}/payments/checkout", json=payload, headers=get_headers())
    
    if resp.status_code != 200:
        print(f"❌ Checkout failed: {resp.text}")
        return
        
    order = resp.json()
    order_id = order["razorpay_order_id"]
    fake_payment_id = f"pay_{uuid.uuid4().hex[:14]}"
    
    # 2. Fire payment.failed webhook
    webhook_payload = {
        "event": "payment.failed",
        "payload": {
            "payment": {"entity": {"id": fake_payment_id, "order_id": order_id}}
        }
    }
    webhook_sig = generate_webhook_signature(webhook_payload)
    webhook_headers = {"x-razorpay-signature": webhook_sig, "Content-Type": "application/json"}
    
    w_resp = await client.post(f"{BASE_URL}/webhooks/razorpay", json=webhook_payload, headers=webhook_headers)
    
    if w_resp.status_code == 200:
        print("✅ payment.failed webhook processed. Promo slot should be freed.")
    else:
        print(f"❌ Webhook failed: {w_resp.status_code} {w_resp.text}")

async def test_over_refund_request(client: httpx.AsyncClient, successful_order: dict):
    print("\n--- Testing Over-Refund Request Limit ---")
    if not successful_order:
        print("⏭️ Skipping (needs successful order from race condition test)")
        return
        
    payment_id = successful_order["payment_id"]
    amount_paid = float(successful_order["amount_paid"])
    
    # Request 80% refund (should succeed)
    amount_1 = round(amount_paid * 0.8, 2)
    resp1 = await client.post(
        f"{BASE_URL}/companies/{COMPANY_ID}/payments/{payment_id}/refund-request",
        json={"amount": amount_1},
        headers=get_headers()
    )
    
    if resp1.status_code == 201:
        print(f"✅ First refund request for {amount_1} succeeded.")
    else:
        print(f"❌ First refund request failed: {resp1.text}")
        return
        
    # Request 30% refund (total 110% -> should fail)
    amount_2 = round(amount_paid * 0.3, 2)
    resp2 = await client.post(
        f"{BASE_URL}/companies/{COMPANY_ID}/payments/{payment_id}/refund-request",
        json={"amount": amount_2},
        headers=get_headers()
    )
    
    if resp2.status_code == 400:
        print(f"✅ Second refund request for {amount_2} correctly rejected (400): {resp2.json()['detail']}")
    else:
        print(f"❌ Second refund request failed validation! Expected 400, got {resp2.status_code}")


async def main():
    if "PASTE_" in COMPANY_ID or "PASTE_" in USER_JWT:
        print("❌ Fill in COMPANY_ID and USER_JWT at the top of the script first!")
        return

    await setup_promo_codes()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        await test_promo_code_failures(client)
        await test_free_order_skip(client)
        successful_order = await test_race_condition(client)
        await test_failed_payment_promo_release(client)
        await test_over_refund_request(client, successful_order)

if __name__ == "__main__":
    asyncio.run(main())
