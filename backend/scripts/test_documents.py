import asyncio
import uuid
import sys
import os
from datetime import datetime, timezone

# Add the backend root directory to Python's path so it can find the 'app' module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from dotenv import dotenv_values

env = dotenv_values("c:/Users/amank/OneDrive/Desktop/production-app-root/backend/.env")

# --- IMPORTANT ---
# Fill these in before running!
BASE_URL = "http://localhost:8000"
COMPANY_ID = "PASTE_COMPANY_ID_HERE"      
USER_JWT = "PASTE_ADMIN_JWT_HERE"         
# -----------------

def get_headers():
    return {
        "Authorization": f"Bearer {USER_JWT}",
        "Content-Type": "application/json"
    }

async def setup_test_documents():
    """Seed the database directly with a rejected document and another company's document."""
    print("\n[Setup] Seeding documents in the database...")
    from app.database import AsyncSessionLocal
    from app.models import Document, Profile, Company, SystemRole, CompanyType, PackType, DocumentStatus, DocumentCategory
    
    cid = uuid.UUID(COMPANY_ID)
    
    dummy_company_id = uuid.uuid4()
    dummy_profile_id = f"dummy_{dummy_company_id.hex[:10]}"
    
    my_rejected_doc_id = uuid.uuid4()
    other_company_doc_id = uuid.uuid4()
    
    async with AsyncSessionLocal() as db:
        # 1. Ensure dummy company exists (for cross-company test)
        db.add(Profile(
            id=dummy_profile_id,
            email=f"{dummy_profile_id}@test.com",
            system_role=SystemRole.BRAND_ADMIN
        ))
        await db.commit()
        
        db.add(Company(
            id=dummy_company_id,
            clerk_org_id=f"org_{dummy_company_id.hex[:10]}",
            owner_id=dummy_profile_id,
            name="Dummy Corp Documents",
            company_type=CompanyType.BRAND,
            pack=PackType.STARTER,
            tier=1
        ))
        await db.commit()

        # Get my profile_id from the database based on COMPANY_ID's owner to satisfy FK
        # In a real scenario, the uploaded_by_profile_id should be the user's ID
        from sqlalchemy import select
        res = await db.execute(select(Company.owner_id).where(Company.id == cid))
        my_profile_id = res.scalar_one_or_none()
        if not my_profile_id:
            print("❌ Setup failed: Could not find owner_id for your COMPANY_ID in the DB.")
            return None, None
            
        # 2. Insert a REJECTED document for MY company
        db.add(Document(
            id=my_rejected_doc_id,
            company_id=cid,
            uploaded_by_profile_id=my_profile_id,
            file_name="invoice.pdf",
            storage_key=f"companies/{cid}/invoice.pdf",
            file_size_bytes=1024,
            file_type="application/pdf",
            category=DocumentCategory.TAX,
            status=DocumentStatus.REJECTED,
            rejection_reason="Blurry image, please re-upload."
        ))
        
        # 3. Insert a VALID document for the DUMMY company
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
    return str(my_rejected_doc_id), str(other_company_doc_id)

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
    if not other_doc_id:
        print("⏭️ Skipping (setup failed)")
        return
        
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
    if not rejected_doc_id:
        print("⏭️ Skipping (setup failed)")
        return
        
    # Verify it is initially rejected
    resp1 = await client.get(f"{BASE_URL}/companies/{COMPANY_ID}/documents", headers=get_headers())
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
    if "PASTE_" in COMPANY_ID or "PASTE_" in USER_JWT:
        print("❌ Fill in COMPANY_ID and USER_JWT at the top of the script first!")
        return

    rejected_doc_id, other_doc_id = await setup_test_documents()
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        await test_malicious_upload(client)
        await test_cross_company_access(client, other_doc_id)
        await test_reupload_reset(client, rejected_doc_id)

if __name__ == "__main__":
    asyncio.run(main())
