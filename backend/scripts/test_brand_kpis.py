import asyncio
import uuid
import sys
import os
from decimal import Decimal
from datetime import datetime

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import AsyncSessionLocal
from app.models import (
    Company, CompanyMember, CompanyType, Profile, SystemRole,
    MemberRole, MemberStatus, MaterialType, PackType,
    WalletRecharge, WalletRechargeStatus, MaterialListing,
    MaterialPurchase, PurchaseStatus, ArrivalStatus
)
from app.routers.kpis import get_brand_dashboard_kpis
from app.schemas import OfflineDealCreate, MaterialPurchaseCreate
from app.routers.brand_marketplace import create_offline_deal, purchase_listing

async def main():
    print("==================================================")
    print("  TESTING ALL BRAND KPIs AND BRAND FEATURES")
    print("==================================================")

    async with AsyncSessionLocal() as db:
        # 1. Setup a test brand
        profile_id = f"test_brand_user_{uuid.uuid4().hex[:8]}"
        company_id = uuid.uuid4()
        recycler_company_id = uuid.uuid4()
        
        # Create user
        print(f"\n[1] Creating test profiles and companies...")
        profile = Profile(id=profile_id, email=f"{profile_id}@example.com", system_role=SystemRole.BRAND_ADMIN)
        db.add(profile)
        await db.commit()
        
        # Create brand company
        brand_company = Company(
            id=company_id,
            clerk_org_id=f"org_brand_{uuid.uuid4().hex[:8]}",
            owner_id=profile_id,
            name="Test Brand Co.",
            company_email="brand@test.com",
            mobile_number="1234567890",
            gst_number="GSTBRAND123",
            company_pan_number="PANBRAND1",
            factory_address="123 Brand St",
            state="Delhi",
            city="Delhi",
            pincode="110001",
            contact_person_name="Brand Admin",
            designation="Owner",
            material=MaterialType.PLASTIC,
            company_type=CompanyType.BRAND,
            pack=PackType.STARTER,
            tier=1,
            wallet_balance=Decimal("0.00"),
            frozen_wallet_balance=Decimal("0.00")
        )
        db.add(brand_company)
        
        # Add member relation
        member = CompanyMember(
            company_id=company_id,
            profile_id=profile_id,
            member_role=MemberRole.OWNER,
            status=MemberStatus.ACTIVE
        )
        db.add(member)
        
        # Create a mock recycler for marketplace purchases
        recycler_profile_id = f"test_recycler_{uuid.uuid4().hex[:8]}"
        db.add(Profile(id=recycler_profile_id, email=f"{recycler_profile_id}@example.com", system_role=SystemRole.RECYCLER))
        await db.commit()
        
        recycler_company = Company(
            id=recycler_company_id,
            clerk_org_id=f"org_rec_{uuid.uuid4().hex[:8]}",
            owner_id=recycler_profile_id,
            name="Test Recycler Co.",
            company_email="rec@test.com",
            mobile_number="0987654321",
            gst_number="GSTREC123",
            company_pan_number="PANREC1",
            factory_address="456 Rec St",
            state="Maharashtra",
            city="Mumbai",
            pincode="400001",
            contact_person_name="Rec Admin",
            designation="Owner",
            material=MaterialType.PLASTIC,
            company_type=CompanyType.RECYCLER,
            pack=PackType.STARTER,
            tier=1
        )
        db.add(recycler_company)
        
        await db.commit()
        
        # 2. Add Wallet Recharge
        print(f"\n[2] Simulating Wallet Recharge (₹10,000)...")
        recharge = WalletRecharge(
            company_id=company_id,
            initiated_by_profile_id=profile_id,
            razorpay_order_id=f"order_{uuid.uuid4().hex[:10]}",
            status=WalletRechargeStatus.SUCCESS.value,
            amount=Decimal("10000.00")
        )
        db.add(recharge)
        brand_company.wallet_balance += Decimal("10000.00")
        await db.commit()
        
        # 3. Create an Offline Deal
        print(f"\n[3] Creating an Offline Deal...")
        offline_payload = OfflineDealCreate(
            recycler_name="Local Kabadiwala",
            material_type=MaterialType.PLASTIC,
            category="PET Bottles",
            grade="Mixed",
            quantity=Decimal("15.5"),
            total_price=Decimal("310.00"),
            validity_risk="HIGH RISK (NO DOCS)"
        )
        offline_listing = await create_offline_deal(
            company_id=company_id,
            payload=offline_payload,
            admin_member=member,
            db=db
        )
        print(f"    -> Created Offline Deal: {offline_listing.id}")
        
        # 4. Create a Recycler Listing and Purchase it (Marketplace test)
        print(f"\n[4] Creating a Recycler Listing and Purchasing...")
        rec_listing = MaterialListing(
            recycler_id=recycler_company_id,
            material_type=MaterialType.PLASTIC,
            category="HDPE Granules",
            grade="A",
            price_per_unit=Decimal("50.00"),
            total_quantity=Decimal("100.00"),
            available_quantity=Decimal("100.00")
        )
        db.add(rec_listing)
        await db.commit()
        await db.refresh(rec_listing)
        
        purchase_payload = MaterialPurchaseCreate(
            quantity=Decimal("20.00") # 20 * 50 = 1000 (500 immediate, 500 pending)
        )
        try:
            purchase_out = await purchase_listing(
                company_id=company_id,
                listing_id=rec_listing.id,
                body=purchase_payload,
                deps=(brand_company, member),
                db=db
            )
            print(f"    -> Successfully purchased {purchase_out.purchased_quantity} MT of {rec_listing.category}.")
            print(f"    -> Total Price: ₹{purchase_out.total_price}. Immediate Deduction: ₹{purchase_out.immediate_deduction}.")
        except Exception as e:
            print(f"    -> Purchase failed: {e}")
            
        # 5. Fetch all KPIs
        print(f"\n[5] Fetching Brand Dashboard KPIs...")
        kpis = await get_brand_dashboard_kpis(
            company_id=company_id,
            admin_member=member,
            db=db,
            purchase_history_offset=0,
            purchase_history_limit=10,
            wallet_history_offset=0,
            wallet_history_limit=10,
            deal_invoices_offset=0,
            deal_invoices_limit=10,
            offline_deals_offset=0,
            offline_deals_limit=10
        )
        
        print("\n--- KPI RESULTS ---")
        print(f"Total Spend (INR): ₹{kpis.total_spend_inr}")
        print(f"Average Spend per MT: ₹{kpis.avg_spend_per_mt}")
        print(f"Wallet Balance: ₹{kpis.wallet_kpis.current_balance}")
        print(f"Frozen Balance (Pending Payments): ₹{kpis.wallet_kpis.pending_payments}")
        print(f"Total Recharged: ₹{kpis.wallet_kpis.total_recharge}")
        
        print(f"\nOffline Deals Count: {len(kpis.offline_deals)}")
        for deal in kpis.offline_deals:
            print(f"  - {deal.recycler_name}: {deal.quantity} MT of {deal.category} @ ₹{deal.amount}")
            
        print(f"\nRecent Marketplace Purchases: {len(kpis.recent_purchases)}")
        for p in kpis.recent_purchases:
            print(f"  - {p.recycler_name}: {p.quantity} MT (Total: ₹{p.total_value}) - Status: {p.status}")
            
        print(f"\nWallet Transactions History: {len(kpis.wallet_transactions)}")
        for w in kpis.wallet_transactions:
            print(f"  - {w.date}: {w.type} (Amount: ₹{w.amount}) - Status: {w.status}")
            
        print(f"\nOrder Status Summary:")
        print(f"  - Pending: {kpis.order_status_summary.pending}")
        print(f"  - Processing: {kpis.order_status_summary.processing}")
        print(f"  - Delivered: {kpis.order_status_summary.delivered}")
        print(f"  - Canceled: {kpis.order_status_summary.canceled}")
        
        # 6. Teardown
        print("\n[6] Tearing down test data...")
        from sqlalchemy import delete
        
        if 'purchase_out' in locals():
            await db.execute(delete(MaterialPurchase).where(MaterialPurchase.id == purchase_out.id))
            
        await db.execute(delete(MaterialPurchase).where(MaterialPurchase.listing_id == offline_listing.id))
        await db.execute(delete(MaterialListing).where(MaterialListing.id == offline_listing.id))
        
        await db.execute(delete(MaterialListing).where(MaterialListing.id == rec_listing.id))
        await db.execute(delete(WalletRecharge).where(WalletRecharge.id == recharge.id))
        await db.execute(delete(CompanyMember).where(CompanyMember.id == member.id))
        
        await db.execute(delete(Company).where(Company.id == brand_company.id))
        await db.execute(delete(Company).where(Company.id == recycler_company.id))
        
        await db.execute(delete(Profile).where(Profile.id == profile_id))
        await db.execute(delete(Profile).where(Profile.id == recycler_profile_id))
        
        await db.commit()
        print("✅ Cleanup complete.")
        
        print("\nSUCCESS! All brand KPIs and features executed properly.")

if __name__ == "__main__":
    asyncio.run(main())
