import asyncio
import uuid
import sys
import os
import requests
from datetime import datetime, timezone
from decimal import Decimal

# Add the backend root directory to Python's path so it can find the 'app' module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from dotenv import dotenv_values

from app.database import AsyncSessionLocal
from app.models import Document, Profile, Company, CompanyMember, SystemRole, CompanyType, PackType, DocumentStatus, DocumentCategory, MaterialType, MemberRole, MemberStatus
from sqlalchemy import delete

env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
env = dotenv_values(env_path)

PORT = env.get("PORT", "8000")
BASE_URL = f"http://localhost:{PORT}"
CLERK_SECRET_KEY = env.get("CLERK_SECRET_KEY", "")
CLERK_API_BASE = "https://api.clerk.com/v1"

# Globals populated at runtime
USER_JWT = ""
USER_ID = ""
COMPANY_ID = None

def get_headers():
    return {
        "Authorization": f"Bearer {USER_JWT}",
        "Content-Type": "application/json"
    }

def provision_clerk_user() -> tuple[str, str]:
    """Creates a temporary Clerk user and mints a session JWT for them."""
    print("\n[Setup] Provisioning temporary Clerk admin user...")
    headers = {"Authorization": f"Bearer {CLERK_SECRET_KEY}", "Content-Type": "application/json"}
    
    email = f"test_docs_{uuid.uuid4().hex[:8]}@example.com"
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

async def setup_test_documents():
    global COMPANY_ID
    print("\n[Setup] Seeding documents in the database...")
    
    dummy_company_id = uuid.uuid4()
    dummy_profile_id = f"dummy_{dummy_company_id.hex[:10]}"
    
    COMPANY_ID = uuid.uuid4()
    my_rejected_doc_id = uuid.uuid4()
    other_company_doc_id = uuid.uuid4()
    
    async with AsyncSessionLocal() as db:
        # Give webhooks time to finish processing if necessary
        await asyncio.sleep(2)
        
        await db.merge(Profile(
            id=USER_ID,
            email=f"{USER_ID}@test.com",
            system_role=SystemRole.BRAND_ADMIN
        ))
        await db.merge(Profile(
            id=dummy_profile_id,
            email=f"{dummy_profile_id}@test.com",
            system_role=SystemRole.BRAND_ADMIN
        ))
        await db.commit()
        
        db.add(Company(
            id=COMPANY_ID,
            clerk_org_id=f"org_{COMPANY_ID.hex[:10]}",
            owner_id=USER_ID,
            name="My Test Company",
            company_type=CompanyType.BRAND,
            pack=PackType.STARTER,
            tier=1,
            material=MaterialType.PLASTIC,
            gst_number="27AAAAA0000A1Z5",
            contact_person_name="Test Person", 
            contact_person_email="test@person.com", 
            company_email="test@company.com", 
            mobile_number="9999999999", 
            company_pan_number="ABCDE1234F", 
            factory_address="123 Test St", 
            state="Maharashtra", 
            city="Mumbai", 
            pincode="400001", 
            company_website="https://test.com", 
            designation="Manager"
        ))
        
        db.add(CompanyMember(
            company_id=COMPANY_ID,
            profile_id=USER_ID,
            member_role=MemberRole.OWNER,
            status=MemberStatus.ACTIVE
        ))
        
        db.add(Company(
            id=dummy_company_id,
            clerk_org_id=f"org_{dummy_company_id.hex[:10]}",
            owner_id=dummy_profile_id,
            name="Dummy Corp Documents",
            company_type=CompanyType.BRAND,
            pack=PackType.STARTER,
            tier=1,
            material=MaterialType.PLASTIC,
            gst_number="27BBBBB0000B1Z5",
            contact_person_name="Dummy Person", 
            contact_person_email="dummy@person.com", 
            company_email="dummy@company.com", 
            mobile_number="8888888888", 
            company_pan_number="FGHIJ5678K", 
            factory_address="456 Dummy St", 
            state="Maharashtra", 
            city="Mumbai", 
            pincode="400002", 
            company_website="https://dummy.com", 
            designation="Director"
        ))
        
        db.add(CompanyMember(
            company_id=dummy_company_id,
            profile_id=dummy_profile_id,
            member_role=MemberRole.OWNER,
            status=MemberStatus.ACTIVE
        ))
        
        await db.commit()

        db.add(Document(
            id=my_rejected_doc_id,
            company_id=COMPANY_ID,
            uploaded_by_profile_id=USER_ID,
            file_name="invoice.pdf",
            storage_key=f"companies/{COMPANY_ID}/invoice.pdf",
            file_size_bytes=1024,
            file_type="application/pdf",
            category=DocumentCategory.TAX,
            status=DocumentStatus.REJECTED,
            rejection_reason="Blurry image, please re-upload."
        ))
        
        db.add(Document(
            id=other_company_doc_id,
            company_id=dummy_company_id,
            uploaded_by_profile_id=dummy_profile_id,
            file_name="secret.pdf",
            storage_key=f"companies/{dummy_company_id}/secret.pdf",
            file_size_bytes=1024,
            file_type="application/pdf",
            category=DocumentCategory.TAX,
            status=DocumentStatus.VERIFIED
        ))
        await db.commit()
        
    print("[Setup] Test documents ready.")
    return str(my_rejected_doc_id), str(other_company_doc_id), dummy_company_id, dummy_profile_id

async def test_malicious_upload(client: httpx.AsyncClient):
    print("\n--- Testing Malicious File Upload Bypass ---")
    payload = {
        "file_name": "virus.exe",
        "file_type": "application/x-msdownload",
        "file_size_bytes": 50000,
        "category": "OTHER"
    }
    
    resp = await client.post(
        f"{BASE_URL}/companies/{COMPANY_ID}/documents/presign",
        json=payload,
        headers=get_headers()
    )
    
    if resp.status_code == 422:
        error = resp.json()["detail"][0]["msg"]
        print(f"✅ Schema validation correctly rejected the malicious file (422): {error}")
    else:
        print(f"❌ Failed! Expected 422, got {resp.status_code}: {resp.text}")

async def test_cross_company_access(client: httpx.AsyncClient, other_doc_id: str):
    print("\n--- Testing Cross-Company Document Access ---")
    # Attempt to download the OTHER company's document using MY company's endpoint
    resp = await client.get(
        f"{BASE_URL}/companies/{COMPANY_ID}/documents/{other_doc_id}/download",
        headers=get_headers()
    )
    
    if resp.status_code == 404:
        print("✅ Correctly received 404 Not Found (cross-company isolation enforced).")
    elif resp.status_code == 403:
        print("✅ Correctly received 403 Forbidden (cross-company isolation enforced).")
    else:
        print(f"❌ Failed! Expected 404 or 403, got {resp.status_code}: {resp.text}")

async def test_reupload_reset(client: httpx.AsyncClient, rejected_doc_id: str):
    print("\n--- Testing Re-Upload Verification Reset ---")
    resp1 = await client.get(f"{BASE_URL}/companies/{COMPANY_ID}/documents", headers=get_headers())
    if resp1.status_code != 200:
        print(f"❌ Failed to fetch documents. Expected 200, got {resp1.status_code}: {resp1.text}")
        return
        
    docs = resp1.json()
    rejected_doc = next((d for d in docs if d["id"] == rejected_doc_id), None)
    if not rejected_doc:
        print("❌ Could not find the rejected document in the API response.")
        return
        
    print(f"  Current Status: {rejected_doc['status']}")
    print(f"  Rejection Reason: {rejected_doc['rejection_reason']}")
    
    # Perform Re-Upload (PUT)
    payload = {
        "file_name": "invoice_clear.pdf",
        "storage_key": f"companies/{COMPANY_ID}/invoice_clear.pdf",
        "file_size_bytes": 2048,
        "file_type": "application/pdf",
        "category": "TAX"
    }
    
    resp2 = await client.put(
        f"{BASE_URL}/companies/{COMPANY_ID}/documents/{rejected_doc_id}",
        json=payload,
        headers=get_headers()
    )
    
    if resp2.status_code == 200:
        updated_doc = resp2.json()
        if updated_doc["status"] == "PENDING_VERIFICATION" and updated_doc["rejection_reason"] is None:
            print("✅ Status reset to PENDING_VERIFICATION and rejection_reason cleared successfully.")
        else:
            print(f"❌ Document updated but status is {updated_doc['status']} and reason is {updated_doc['rejection_reason']}")
    else:
        print(f"❌ PUT request failed with {resp2.status_code}: {resp2.text}")

async def main():
    global USER_JWT, USER_ID, COMPANY_ID
    
    my_doc_id = None
    other_doc_id = None
    dummy_co_id = None
    dummy_prof_id = None
    
    if not CLERK_SECRET_KEY:
        print("❌ CLERK_SECRET_KEY is missing from .env. Cannot provision test user.")
        sys.exit(1)
        
    try:
        USER_ID, USER_JWT = provision_clerk_user()
        my_doc_id, other_doc_id, dummy_co_id, dummy_prof_id = await setup_test_documents()
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            await test_malicious_upload(client)
            await test_cross_company_access(client, other_doc_id)
            await test_reupload_reset(client, my_doc_id)
            
    finally:
        if USER_ID:
            print("\n[Teardown] Cleaning up database...")
            async with AsyncSessionLocal() as db:
                if my_doc_id: await db.execute(delete(Document).where(Document.id == str(my_doc_id)))
                if other_doc_id: await db.execute(delete(Document).where(Document.id == str(other_doc_id)))
                
                if COMPANY_ID: await db.execute(delete(CompanyMember).where(CompanyMember.company_id == COMPANY_ID))
                if dummy_co_id: await db.execute(delete(CompanyMember).where(CompanyMember.company_id == dummy_co_id))
                
                if COMPANY_ID: await db.execute(delete(Company).where(Company.id == COMPANY_ID))
                if dummy_co_id: await db.execute(delete(Company).where(Company.id == dummy_co_id))
                
                await db.execute(delete(Profile).where(Profile.id == USER_ID))
                if dummy_prof_id: await db.execute(delete(Profile).where(Profile.id == dummy_prof_id))
                await db.commit()
            
            delete_clerk_user(USER_ID)
        
if __name__ == "__main__":
    asyncio.run(main())
