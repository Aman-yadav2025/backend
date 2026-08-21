import asyncio
import uuid
import sys
import os
from datetime import datetime, timezone

# Add the backend root directory to Python's path so it can find the 'app' module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from dotenv import dotenv_values

env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
env = dotenv_values(env_path)

# --- IMPORTANT ---
# Fill these in before running!
BASE_URL = "http://localhost:8000"
USER_JWT = "eyJhbGciOiJSUzI1NiIsImNhdCI6ImNsX0I3ZDRQRDIyMkFBQSIsImtpZCI6Imluc18zSHpHVjhYa1BKMTdVblJyMmJTbFFkejN1SjAiLCJ0eXAiOiJKV1QifQ.eyJleHAiOjE3ODc0MzgxMjMsImlhdCI6MTc4NzM1MTcyMywiaXNzIjoiaHR0cHM6Ly9mbGV4aWJsZS1zd2luZS01NDExLmNsZXJrLmFjY291bnRzLmRldiIsImp0aSI6ImVhYTMxZGRjMmE2ZThkNDhhNTYzIiwibmJmIjoxNzg3MzUxNzE4LCJzdWIiOiJ1c2VyXzNJQksxMmhjSGhHMUpYZWFXakQ0TUw3UGNSUiJ9.M0Cykm8uqCZ8s2uYQnN8vFWVR85jsqvNVz7fwRb054IVUet8ZWdlN9zQ75atiqVrVvYVdLHYrjPQQDDtzTvikCW0C1JuXldAdIC5Lfxa0jfDWykp6pyLSayGqVQC_aVnwEciJ3GIcGPtDQLUe74uxEE1WxOmmCGzJlkyXR_tQLm7-qmH2mrXwPeMZh93pM_R_PZVaDsUZeyoTEIS0P-15ZIk-csKz1VfeIV1ObpK_I90wKpagJ3UMFqILWzPGNU-RNHqQ0bmx9YTXHy3aGZoUpyHFrcklcg_ZWIx1tzHTaWl1OooqS5fKP9gt5PWzoSSognbAypN-61loQrLxIdt_Q"         
# -----------------

def get_headers():
    return {
        "Authorization": f"Bearer {USER_JWT}",
        "Content-Type": "application/json"
    }

def get_profile_id_from_jwt(jwt_token: str) -> str:
    import jwt
    decoded = jwt.decode(jwt_token, options={"verify_signature": False})
    return decoded.get("sub")

async def setup_admin_data():
    print("\n[Setup] Upgrading your profile to PLATFORM_ADMIN and seeding test data...")
    from app.database import AsyncSessionLocal
    from app.models import (
        Profile, SystemRole, Document, Payment, RefundRequest, 
        Company, CompanyType, PackType, DocumentCategory, DocumentStatus, 
        PaymentStatus, RefundRequestStatus
    )
    
    profile_id = get_profile_id_from_jwt(USER_JWT)
    if not profile_id:
        print("❌ Could not decode JWT to find your profile ID.")
        return None
        
    dummy_company_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    
    # Concurrent Test Data
    payment_concurrent_id = uuid.uuid4()
    refund_req_1_id = uuid.uuid4()
    refund_req_2_id = uuid.uuid4()
    
    # Reset Status Test Data
    payment_reset_id = uuid.uuid4()
    refund_req_approved_id = uuid.uuid4()
    refund_req_pending_id = uuid.uuid4()
    
    async with AsyncSessionLocal() as db:
        # 1. Upgrade user to PLATFORM_ADMIN
        from sqlalchemy import select
        res = await db.execute(select(Profile).where(Profile.id == profile_id))
        profile = res.scalar_one_or_none()
        if profile:
            profile.system_role = SystemRole.PLATFORM_ADMIN
            await db.commit()
        else:
            print(f"❌ Could not find profile {profile_id} in DB.")
            return None
            
        # 2. Dummy Company for relationships
        res_comp = await db.execute(select(Company).where(Company.owner_id == profile_id))
        existing_company = res_comp.scalar_one_or_none()
        if existing_company:
            dummy_company_id = existing_company.id
        else:
            db.add(Company(
                id=dummy_company_id,
                clerk_org_id=f"org_{dummy_company_id.hex[:10]}",
                owner_id=profile_id,
                name="Admin Test Corp",
                company_type=CompanyType.BRAND,
                pack=PackType.STARTER,
                tier=1
            ))
            await db.commit()
        
        # 3. Dummy Document
        random_suffix = uuid.uuid4().hex[:6]
        db.add(Document(
            id=doc_id,
            company_id=dummy_company_id,
            uploaded_by_profile_id=profile_id,
            file_name=f"admin_test_{random_suffix}.pdf",
            storage_key=f"companies/{dummy_company_id}/admin_test_{random_suffix}.pdf",
            file_size_bytes=1024,
            file_type="application/pdf",
            category=DocumentCategory.TAX,
            status=DocumentStatus.PENDING_VERIFICATION
        ))
        
        # 4. Data for Concurrent Refunds (Payment amount=1000, two refunds=600 each)
        db.add(Payment(
            id=payment_concurrent_id,
            company_id=dummy_company_id,
            initiated_by_profile_id=profile_id,
            razorpay_order_id=f"order_dummy_{payment_concurrent_id.hex[:10]}",
            razorpay_payment_id=f"pay_dummy_{payment_concurrent_id.hex[:10]}",
            status=PaymentStatus.SUCCESS,
            original_amount=1000,
            amount_paid=1000,
            currency="INR",
            plan_package=PackType.GROWTH,
            plan_tier=1
        ))
        await db.commit()
        
        db.add(RefundRequest(
            id=refund_req_1_id,
            payment_id=payment_concurrent_id,
            requested_by_profile_id=profile_id,
            amount=600,
            status=RefundRequestStatus.PENDING
        ))
        db.add(RefundRequest(
            id=refund_req_2_id,
            payment_id=payment_concurrent_id,
            requested_by_profile_id=profile_id,
            amount=600,
            status=RefundRequestStatus.PENDING
        ))
        
        # 5. Data for Status Reset (Payment=1000, one approved=400, one pending=300)
        db.add(Payment(
            id=payment_reset_id,
            company_id=dummy_company_id,
            initiated_by_profile_id=profile_id,
            razorpay_order_id=f"order_dummy_{payment_reset_id.hex[:10]}",
            razorpay_payment_id=f"pay_dummy_{payment_reset_id.hex[:10]}",
            status=PaymentStatus.PENDING_REFUND,
            original_amount=1000,
            amount_paid=1000,
            currency="INR",
            plan_package=PackType.GROWTH,
            plan_tier=1
        ))
        await db.commit()
        
        db.add(RefundRequest(
            id=refund_req_approved_id,
            payment_id=payment_reset_id,
            requested_by_profile_id=profile_id,
            amount=400,
            status=RefundRequestStatus.APPROVED,
            razorpay_refund_id=f"rfnd_{refund_req_approved_id.hex[:10]}",
            actioned_by=profile_id,
            actioned_at=datetime.now(timezone.utc)
        ))
        db.add(RefundRequest(
            id=refund_req_pending_id,
            payment_id=payment_reset_id,
            requested_by_profile_id=profile_id,
            amount=300,
            status=RefundRequestStatus.PENDING
        ))
        
        await db.commit()
        
    print("[Setup] Test admin data ready.")
    return {
        "doc_id": str(doc_id),
        "concurrent": [str(refund_req_1_id), str(refund_req_2_id)],
        "reset": str(refund_req_pending_id),
        "reset_payment_id": str(payment_reset_id),
        "profile_id": profile_id
    }

async def test_document_verification_constraints(client: httpx.AsyncClient, data: dict):
    print("\n--- Testing Document Verification Constraints & Audit Trail ---")
    doc_id = data["doc_id"]
    profile_id = data["profile_id"]
    
    # 1. Attempt to pass PENDING_VERIFICATION (should fail Literal type check)
    resp1 = await client.patch(
        f"{BASE_URL}/admin/documents/{doc_id}/verify",
        json={"status": "PENDING_VERIFICATION"},
        headers=get_headers()
    )
    if resp1.status_code == 422:
        print("✅ PENDING_VERIFICATION correctly rejected by Pydantic Literal typing (422).")
    else:
        print(f"❌ Failed! Expected 422, got {resp1.status_code}: {resp1.text}")
        
    # 2. Attempt to verify properly
    resp2 = await client.patch(
        f"{BASE_URL}/admin/documents/{doc_id}/verify",
        json={"status": "VERIFIED"},
        headers=get_headers()
    )
    if resp2.status_code == 200:
        doc = resp2.json()
        if doc["verified_by"] == profile_id and doc["verified_at"] is not None:
            print("✅ Document VERIFIED successfully, and Audit Trail (verified_by/at) was accurately recorded.")
        else:
            print("❌ Document verified, but Audit Trail data is missing!")
    else:
        print(f"❌ Verification failed with {resp2.status_code}: {resp2.text}")

async def test_concurrent_refund_approvals(client: httpx.AsyncClient, data: dict):
    print("\n--- Testing Concurrent Refund Approvals (Critical Race) ---")
    req_1, req_2 = data["concurrent"]
    
    # We fire both approvals at the exact same millisecond. 
    # Because 600 + 600 > 1000, one MUST fail with 400, and one MUST succeed with 200.
    # If both succeed, we have a race condition over-refunding money.
    print("Firing two 600 INR refund approvals for a 1000 INR payment concurrently...")
    
    async def approve(req_id):
        r = await client.post(f"{BASE_URL}/admin/refund-requests/{req_id}/approve", headers=get_headers())
        return (req_id, r.status_code, r.text)
        
    results = await asyncio.gather(approve(req_1), approve(req_2))
    
    success_count = 0
    fail_count = 0
    audit_trail_ok = False
    
    for req_id, status, text in results:
        flag = "✅" if status in [200, 400] else "❌"
        print(f"  {flag}  [{status}]  Refund Request: {req_id}")
        if status == 200:
            success_count += 1
            body = json.loads(text)
            if body["actioned_by"] == data["profile_id"] and body["actioned_at"] is not None:
                audit_trail_ok = True
        elif status == 400:
            fail_count += 1
            
    if success_count == 1 and fail_count == 1:
        print("✅ Race Condition Prevented: Row lock successfully stopped the over-refund before calling Razorpay.")
        if audit_trail_ok:
            print("✅ Audit Trail (actioned_by/at) correctly recorded on the successful refund.")
        else:
            print("❌ Audit Trail missing on successful refund!")
    else:
        print(f"❌ CRITICAL FAILURE! Expected exactly 1 success and 1 fail. Got: {success_count} successes, {fail_count} fails.")

async def test_safe_payment_status_reset(client: httpx.AsyncClient, data: dict):
    print("\n--- Testing Safe Payment Status Reset ---")
    req_id = data["reset"]
    
    # Payment currently has 1 approved refund and 1 pending refund.
    # Status is currently PENDING_REFUND.
    # We will reject the pending one. It should revert to PARTIALLY_REFUNDED (not SUCCESS).
    resp = await client.post(
        f"{BASE_URL}/admin/refund-requests/{req_id}/reject",
        headers=get_headers()
    )
    
    if resp.status_code == 200:
        print("✅ Pending refund request correctly rejected.")
    else:
        print(f"❌ Reject failed: {resp.status_code} {resp.text}")
        return
        
    # Verify the Payment status in DB directly
    from app.database import AsyncSessionLocal
    from app.models import Payment
    from sqlalchemy import select
    
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Payment).where(Payment.id == uuid.UUID(data["reset_payment_id"])))
        payment = res.scalar_one()
        
        print(f"  Resulting Payment Status: {payment.status.name}")
        if payment.status.name == "PARTIALLY_REFUNDED":
            print("✅ Payment status correctly reverted to PARTIALLY_REFUNDED based on SUM of approved refunds.")
        else:
            print(f"❌ Payment status is {payment.status.name}, expected PARTIALLY_REFUNDED.")

import json

async def main():
    if "PASTE_" in USER_JWT:
        print("❌ Fill in USER_JWT at the top of the script first!")
        return

    data = await setup_admin_data()
    if not data:
        return
        
    async with httpx.AsyncClient(timeout=10.0) as client:
        await test_document_verification_constraints(client, data)
        await test_concurrent_refund_approvals(client, data)
        await test_safe_payment_status_reset(client, data)

if __name__ == "__main__":
    asyncio.run(main())
