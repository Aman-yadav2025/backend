import asyncio
import uuid
import sys
import os
import httpx
import requests
from decimal import Decimal
from datetime import datetime
from dotenv import dotenv_values

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
env = dotenv_values(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

BASE_URL = "http://localhost:8000"
CLERK_SECRET_KEY = env.get("CLERK_SECRET_KEY", "")
CLERK_API_BASE = "https://api.clerk.com/v1"

class TestContext:
    company_id: str
    user_jwt: str
    clerk_user_id: str
    brand_company_id: str
    brand_profile_id: str
    collector_deal_id: str
    listing_id: str
    document_id: str

def get_headers(ctx: TestContext):
    return {
        "Authorization": f"Bearer {ctx.user_jwt}",
        "Content-Type": "application/json"
    }

def provision_clerk_user() -> tuple[str, str]:
    print("\n[Setup] Provisioning temporary Clerk user...")
    headers = {"Authorization": f"Bearer {CLERK_SECRET_KEY}", "Content-Type": "application/json"}
    email = f"test_filters_{uuid.uuid4().hex[:8]}@example.com"
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
    from app.models import Profile, Company, CompanyType, PackType, SystemRole, CompanyMember, MemberRole, MemberStatus, MaterialType, CollectorPurchase, MaterialListing, MaterialPurchase, PurchaseStatus, ArrivalStatus, Document, DocumentCategory
    
    ctx.company_id = str(uuid.uuid4())
    ctx.brand_company_id = str(uuid.uuid4())
    ctx.brand_profile_id = str(uuid.uuid4())
    ctx.collector_deal_id = str(uuid.uuid4())
    ctx.listing_id = str(uuid.uuid4())
    ctx.document_id = str(uuid.uuid4())

    async with AsyncSessionLocal() as db:
        await asyncio.sleep(2)
        await db.merge(Profile(id=ctx.clerk_user_id, email=f"{ctx.clerk_user_id}@test.com", system_role=SystemRole.RECYCLER))
        await db.merge(Profile(id=ctx.brand_profile_id, email=f"{ctx.brand_profile_id}@test.com", system_role=SystemRole.BRAND_ADMIN))
        await db.commit()
        
        db.add(Company(id=uuid.UUID(ctx.company_id), clerk_org_id=f"org_{ctx.company_id[:10]}", owner_id=ctx.clerk_user_id, name="Test Recycler Co.", company_type=CompanyType.RECYCLER, pack=PackType.STARTER, tier=1, wallet_balance=0, frozen_wallet_balance=0, gst_number="27AAAAA0000A1Z5", contact_person_name="Test Person", contact_person_email="test@person.com", company_email="test@company.com", mobile_number="9999999999", company_pan_number="ABCDE1234F", factory_address="123 Test St", state="Maharashtra", city="Mumbai", pincode="400001", company_website="https://test.com", designation="Manager", material=MaterialType.PLASTIC))
        db.add(Company(id=uuid.UUID(ctx.brand_company_id), clerk_org_id=f"org_{ctx.brand_company_id[:10]}", owner_id=ctx.brand_profile_id, name="Test Brand Co.", company_type=CompanyType.BRAND, pack=PackType.STARTER, tier=1, wallet_balance=0, frozen_wallet_balance=0, gst_number="27AAAAA0000A1Z5", contact_person_name="Test Person", contact_person_email="test@person.com", company_email="test@company.com", mobile_number="9999999999", company_pan_number="ABCDE1234F", factory_address="123 Test St", state="Maharashtra", city="Mumbai", pincode="400001", company_website="https://test.com", designation="Manager", material=MaterialType.PLASTIC))
        await db.commit()
        
        db.add(CompanyMember(company_id=uuid.UUID(ctx.company_id), profile_id=ctx.clerk_user_id, member_role=MemberRole.OWNER, status=MemberStatus.ACTIVE))
        await db.commit()
        
        db.add(CollectorPurchase(id=uuid.UUID(ctx.collector_deal_id), recycler_id=uuid.UUID(ctx.company_id), collector_name="Ramesh Kabadi", collector_company_name="Ramesh Scraps", mobile_number="9999999999", gst_number="GSTKABADI", address="Street 4, Delhi", category=MaterialType.PLASTIC, material_type="PET Bottles", quantity=Decimal("500.00"), price=Decimal("15000.00")))
        listing = MaterialListing(id=uuid.UUID(ctx.listing_id), recycler_id=uuid.UUID(ctx.company_id), material_type=MaterialType.PLASTIC, category="PET Granules", grade="A", price_per_unit=Decimal("40.00"), total_quantity=Decimal("1000.00"), available_quantity=Decimal("800.00"))
        db.add(listing)
        await db.flush()
        db.add(MaterialPurchase(listing_id=listing.id, brand_id=uuid.UUID(ctx.brand_company_id), category="PET Granules", purchased_quantity=Decimal("100.00"), total_price=Decimal("4000.00"), purchase_type="MARKETPLACE", purchase_status=PurchaseStatus.CONFIRMED, arrival_status=ArrivalStatus.IN_TRANSIT))
        db.add(Document(id=uuid.UUID(ctx.document_id), company_id=uuid.UUID(ctx.company_id), uploaded_by_profile_id=ctx.clerk_user_id, file_name="test_receipt.pdf", storage_key=f"companies/{ctx.company_id}/test_receipt.pdf", file_size_bytes=1024, file_type="application/pdf", category=DocumentCategory.COLLECTOR_RECEIPT))
        
        await db.commit()
        print("✅ Database seeding complete.")

async def teardown_db_data(ctx: TestContext):
    print("\n[Teardown] Cleaning up database...")
    from app.database import AsyncSessionLocal
    from sqlalchemy import delete
    from app.models import Profile, Company, CompanyMember, CollectorPurchase, MaterialListing, MaterialPurchase, Document, InvoiceProof
    
    async with AsyncSessionLocal() as db:
        try:
            await db.execute(delete(InvoiceProof).where(InvoiceProof.recycler_id == uuid.UUID(ctx.company_id)))
            await db.execute(delete(Document).where(Document.company_id == uuid.UUID(ctx.company_id)))
            await db.execute(delete(MaterialPurchase).where(MaterialPurchase.brand_id == uuid.UUID(ctx.brand_company_id)))
            await db.execute(delete(MaterialListing).where(MaterialListing.recycler_id == uuid.UUID(ctx.company_id)))
            await db.execute(delete(CollectorPurchase).where(CollectorPurchase.recycler_id == uuid.UUID(ctx.company_id)))
            await db.execute(delete(CompanyMember).where(CompanyMember.company_id == uuid.UUID(ctx.company_id)))
            await db.execute(delete(Company).where(Company.id.in_([uuid.UUID(ctx.company_id), uuid.UUID(ctx.brand_company_id)])))
            await db.execute(delete(Profile).where(Profile.id.in_([ctx.clerk_user_id, ctx.brand_profile_id])))
            await db.commit()
            print("✅ Database cleanup complete.")
        except Exception as e:
            print(f"⚠️ Warning: DB Teardown failed: {e}")
            await db.rollback()

async def test_advanced_filters(client: httpx.AsyncClient, ctx: TestContext):
    print("\n--- Testing Wallet Review Filters ---")
    resp = await client.get(f"{BASE_URL}/companies/{ctx.company_id}/kpis/wallet-review?company_name=Brand&status=In Transit&min_amount=100", headers=get_headers(ctx))
    assert resp.status_code == 200, resp.text
    print("✅ Wallet Review with advanced filters succeeded.")
    
    print("\n--- Testing Invoice Ledger Filters ---")
    resp = await client.get(f"{BASE_URL}/companies/{ctx.company_id}/kpis/invoice-ledger?deal_type=SALE&party_name=Brand&category=PET", headers=get_headers(ctx))
    assert resp.status_code == 200, resp.text
    print("✅ Invoice Ledger with advanced filters succeeded.")

    print("\n--- Testing Document Vault Filters ---")
    resp = await client.get(f"{BASE_URL}/companies/{ctx.company_id}/documents?document_name=receipt&category=COLLECTOR_RECEIPT", headers=get_headers(ctx))
    assert resp.status_code == 200, resp.text
    print("✅ Document Vault with advanced filters succeeded.")

    print("\n--- Testing Recycler Marketplace Orders ---")
    resp = await client.get(f"{BASE_URL}/companies/{ctx.company_id}/listings/orders", headers=get_headers(ctx))
    assert resp.status_code == 200, resp.text
    print("✅ Marketplace Orders fetched successfully.")

    print("\n--- Testing Collector Purchases Filters ---")
    resp = await client.get(f"{BASE_URL}/companies/{ctx.company_id}/collector-purchases?party_name=Ramesh&min_amount=1000", headers=get_headers(ctx))
    assert resp.status_code == 200, resp.text
    print("✅ Collector Purchases with advanced filters succeeded.")


async def main():
    if not CLERK_SECRET_KEY:
        print("❌ Missing CLERK_SECRET_KEY in .env.")
        return

    ctx = TestContext()
    ctx.clerk_user_id, ctx.user_jwt = provision_clerk_user()
    
    try:
        await setup_db_data(ctx)
        async with httpx.AsyncClient(timeout=30.0) as client:
            await test_advanced_filters(client, ctx)
    finally:
        await teardown_db_data(ctx)
        delete_clerk_user(ctx.clerk_user_id)
        
    print("\n✅ All tests complete.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
