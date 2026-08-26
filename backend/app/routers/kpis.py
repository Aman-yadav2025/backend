import uuid
from decimal import Decimal
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, text, Integer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import (
    Company,
    CompanyType,
    CompanyMember,
    Document,
    DocumentStatus,
    MemberStatus,
    Payment,
    PaymentStatus,
    RefundRequest,
    RefundRequestStatus,
    MaterialPurchase,
    MaterialListing,
    PurchaseStatus,
    ArrivalStatus,
    WalletRecharge,
    WalletRechargeStatus,
)
from app.schemas import (
    CompanyDashboardKPIs, DocumentKPIs, FinancialKPIs, TeamKPIs,
    BrandDashboardKPIs, EPRKPIs, MaterialPurchaseBreakdownItem,
    MonthlyPurchaseTrendItem, OrderStatusSummary, TopRecyclerItem, 
    DashboardPurchaseHistoryItem, WalletTransactionItem, WalletKPIs,
    DashboardDealInvoiceItem
)
from app.security import require_company_admin

router = APIRouter(prefix="/companies/{company_id}/kpis", tags=["kpis"])


@router.get("", response_model=CompanyDashboardKPIs)
async def get_company_kpis(
    company_id: uuid.UUID,
    admin_member: CompanyMember = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns aggregated lifetime KPIs for a company.
    Restricted to Company Admins/Owners due to financial data exposure.
    """
    # 1. Get Company details (pack, tier)
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # 2. Team Metrics
    # In a single query, we count total members and conditionally count active/invited members
    team_result = await db.execute(
        select(
            func.count(CompanyMember.id),
            func.sum(
                func.cast(CompanyMember.status == MemberStatus.ACTIVE, Integer)
            ),
            func.sum(
                func.cast(CompanyMember.status == MemberStatus.INVITED, Integer)
            ),
        ).where(CompanyMember.company_id == company_id)
    )
    team_row = team_result.one()
    total_members = team_row[0] or 0
    active_members = team_row[1] or 0
    pending_invites = team_row[2] or 0

    # 3. Document Metrics
    doc_result = await db.execute(
        select(
            func.count(Document.id),
            func.sum(
                func.cast(Document.status == DocumentStatus.PENDING_VERIFICATION, Integer)
            ),
            func.sum(
                func.cast(Document.status == DocumentStatus.VERIFIED, Integer)
            ),
            func.sum(
                func.cast(Document.status == DocumentStatus.REJECTED, Integer)
            ),
        ).where(Document.company_id == company_id)
    )
    doc_row = doc_result.one()
    total_docs = doc_row[0] or 0
    pending_docs = doc_row[1] or 0
    verified_docs = doc_row[2] or 0
    rejected_docs = doc_row[3] or 0

    # 4. Financial Metrics
    # Lifetime spend includes SUCCESS, PENDING_REFUND, and PARTIALLY_REFUNDED
    spend_result = await db.execute(
        select(func.sum(Payment.amount_paid)).where(
            Payment.company_id == company_id,
            Payment.status.in_([
                PaymentStatus.SUCCESS,
                PaymentStatus.PENDING_REFUND,
                PaymentStatus.PARTIALLY_REFUNDED,
            ])
        )
    )
    lifetime_spend = spend_result.scalar() or Decimal("0.00")

    # To calculate refunds, we must join Payment and RefundRequest for the company
    refund_result = await db.execute(
        select(func.sum(RefundRequest.amount))
        .join(Payment, RefundRequest.payment_id == Payment.id)
        .where(
            Payment.company_id == company_id,
            RefundRequest.status == RefundRequestStatus.APPROVED,
        )
    )
    total_refunded = refund_result.scalar() or Decimal("0.00")
    
    net_spend = Decimal(str(lifetime_spend)) - Decimal(str(total_refunded))

    return CompanyDashboardKPIs(
        company_id=company_id,
        pack=company.pack,
        tier=company.tier,
        team=TeamKPIs(
            total_members=total_members,
            active_members=active_members,
            pending_invites=pending_invites,
        ),
        documents=DocumentKPIs(
            total_uploaded=total_docs,
            pending_verification=pending_docs,
            verified=verified_docs,
            rejected=rejected_docs,
        ),
        financials=FinancialKPIs(
            lifetime_spend_inr=lifetime_spend,
            total_refunded_inr=total_refunded,
            net_spend_inr=net_spend,
        ),
    )


# ============================================================================
# BRAND DASHBOARD KPIs
# ============================================================================

async def get_material_purchased_breakdown(
    db: AsyncSession, company_id: uuid.UUID, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
) -> list[MaterialPurchaseBreakdownItem]:
    query = (
        select(
            MaterialListing.material_type,
            MaterialListing.category,
            func.sum(MaterialPurchase.purchased_quantity).label("total_quantity")
        )
        .join(MaterialListing, MaterialPurchase.listing_id == MaterialListing.id)
        .where(
            MaterialPurchase.brand_id == company_id,
            MaterialPurchase.purchase_status != PurchaseStatus.CANCELLED
        )
        .group_by(MaterialListing.material_type, MaterialListing.category)
    )
    if start_date:
        query = query.where(MaterialPurchase.created_at >= start_date)
    if end_date:
        query = query.where(MaterialPurchase.created_at <= end_date)

    result = await db.execute(query)
    rows = result.all()
    
    return [
        MaterialPurchaseBreakdownItem(
            material_type=row.material_type.value if hasattr(row.material_type, "value") else str(row.material_type),
            category=row.category,
            total_quantity=row.total_quantity or Decimal("0.00")
        )
        for row in rows
    ]


async def get_financials(
    db: AsyncSession, company_id: uuid.UUID
) -> tuple[Decimal, Decimal]:
    query = (
        select(
            func.sum(MaterialPurchase.total_price),
            func.sum(MaterialPurchase.purchased_quantity)
        )
        .where(
            MaterialPurchase.brand_id == company_id,
            MaterialPurchase.purchase_status != PurchaseStatus.CANCELLED
        )
    )
    result = await db.execute(query)
    row = result.one()
    total_spend = row[0] or Decimal("0.00")
    total_quantity = row[1] or Decimal("0.00")
    
    avg_spend = (total_spend / total_quantity) if total_quantity > Decimal("0") else Decimal("0.00")
    return total_spend, avg_spend


async def get_unique_recyclers_count(
    db: AsyncSession, company_id: uuid.UUID
) -> int:
    query = (
        select(func.count(func.distinct(MaterialListing.recycler_id)))
        .select_from(MaterialPurchase)
        .join(MaterialListing, MaterialPurchase.listing_id == MaterialListing.id)
        .where(
            MaterialPurchase.brand_id == company_id,
            MaterialPurchase.purchase_status != PurchaseStatus.CANCELLED
        )
    )
    result = await db.execute(query)
    return result.scalar() or 0


async def get_monthly_trend(
    db: AsyncSession, company_id: uuid.UUID, start_date: Optional[datetime], end_date: Optional[datetime]
) -> list[MonthlyPurchaseTrendItem]:
    query = (
        select(
            func.date_trunc('month', MaterialPurchase.created_at).label("month"),
            func.sum(MaterialPurchase.purchased_quantity).label("total_quantity"),
            func.sum(MaterialPurchase.total_price).label("total_price")
        )
        .where(
            MaterialPurchase.brand_id == company_id,
            MaterialPurchase.purchase_status != PurchaseStatus.CANCELLED
        )
        .group_by(text("month"))
        .order_by(text("month"))
    )
    if start_date:
        query = query.where(MaterialPurchase.created_at >= start_date)
    if end_date:
        query = query.where(MaterialPurchase.created_at <= end_date)

    result = await db.execute(query)
    rows = result.all()
    
    trend = []
    for row in rows:
        qty = row.total_quantity or Decimal("0.00")
        price = row.total_price or Decimal("0.00")
        avg = (price / qty) if qty > 0 else Decimal("0.00")
        
        # In SQLAlchemy, date_trunc returns a datetime
        month_str = row.month.strftime('%Y-%m') if row.month else ""
        if month_str:
            trend.append(MonthlyPurchaseTrendItem(
                month=month_str,
                total_quantity=qty,
                average_rate=avg
            ))
            
    return trend


async def get_top_recyclers(
    db: AsyncSession, company_id: uuid.UUID, offset: int = 0, limit: int = 5
) -> list[TopRecyclerItem]:
    query = (
        select(
            MaterialListing.recycler_id,
            Company.name,
            func.sum(MaterialPurchase.purchased_quantity).label("total_quantity"),
            func.sum(MaterialPurchase.total_price).label("total_value")
        )
        .select_from(MaterialPurchase)
        .join(MaterialListing, MaterialPurchase.listing_id == MaterialListing.id)
        .join(Company, MaterialListing.recycler_id == Company.id)
        .where(
            MaterialPurchase.brand_id == company_id,
            MaterialPurchase.purchase_status != PurchaseStatus.CANCELLED
        )
        .group_by(MaterialListing.recycler_id, Company.name)
        .order_by(func.sum(MaterialPurchase.purchased_quantity).desc())
        .offset(offset)
        .limit(limit)
    )
    
    result = await db.execute(query)
    rows = result.all()
    return [
        TopRecyclerItem(
            recycler_id=row.recycler_id,
            recycler_name=row.name,
            total_quantity=row.total_quantity or Decimal("0.00"),
            total_value=row.total_value or Decimal("0.00")
        )
        for row in rows
    ]


async def get_order_status_summary(
    db: AsyncSession, company_id: uuid.UUID
) -> OrderStatusSummary:
    query = (
        select(
            func.sum(func.cast(MaterialPurchase.arrival_status == ArrivalStatus.DELIVERED, Integer)).label("delivered"),
            func.sum(func.cast((MaterialPurchase.purchase_status == PurchaseStatus.CONFIRMED) & (MaterialPurchase.arrival_status != ArrivalStatus.DELIVERED), Integer)).label("processed"),
            func.sum(func.cast(MaterialPurchase.purchase_status == PurchaseStatus.PENDING, Integer)).label("pending"),
            func.sum(func.cast(MaterialPurchase.purchase_status == PurchaseStatus.CANCELLED, Integer)).label("canceled"),
        )
        .where(MaterialPurchase.brand_id == company_id)
    )
    result = await db.execute(query)
    row = result.one()
    return OrderStatusSummary(
        delivered=row.delivered or 0,
        processed=row.processed or 0,
        pending=row.pending or 0,
        canceled=row.canceled or 0,
    )


async def get_recent_purchases(
    db: AsyncSession, company_id: uuid.UUID, offset: int = 0, limit: int = 10
) -> list[DashboardPurchaseHistoryItem]:
    query = (
        select(
            MaterialPurchase,
            Company.name.label("recycler_name")
        )
        .join(MaterialListing, MaterialPurchase.listing_id == MaterialListing.id)
        .join(Company, MaterialListing.recycler_id == Company.id)
        .where(MaterialPurchase.brand_id == company_id)
        .order_by(MaterialPurchase.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(query)
    rows = result.all()
    
    items = []
    for row in rows:
        p = row.MaterialPurchase
        if p.purchase_status == PurchaseStatus.CANCELLED:
            status = "Canceled"
        elif p.purchase_status == PurchaseStatus.CONFIRMED:
            status = "Success"
        else:
            status = "Pending"
            
        rate = (p.total_price / p.purchased_quantity) if p.purchased_quantity > 0 else Decimal("0.00")
        
        items.append(
            DashboardPurchaseHistoryItem(
                po_id=str(p.listing_id)[:8].upper(),
                recycler_name=row.recycler_name,
                material_type=p.category,
                quantity=p.purchased_quantity,
                rate=rate,
                total_value=p.total_price,
                order_date=p.created_at,
                status=status
            )
        )
    return items


async def get_deal_invoices(
    db: AsyncSession, company_id: uuid.UUID, offset: int = 0, limit: int = 10
) -> list[DashboardDealInvoiceItem]:
    query = (
        select(
            MaterialPurchase,
            MaterialListing,
            Company.name.label("recycler_name"),
            Document.storage_key.label("document_url")
        )
        .join(MaterialListing, MaterialPurchase.listing_id == MaterialListing.id)
        .join(Company, MaterialListing.recycler_id == Company.id)
        .outerjoin(Document, MaterialListing.invoice_document_id == Document.id)
        .where(MaterialPurchase.brand_id == company_id)
        .order_by(MaterialPurchase.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(query)
    rows = result.all()
    
    items = []
    for row in rows:
        p = row.MaterialPurchase
        l = row.MaterialListing
        cat_val = l.material_type.value if hasattr(l.material_type, "value") else str(l.material_type)
        items.append(
            DashboardDealInvoiceItem(
                invoice_no=str(p.id)[:8].upper(),
                date=p.created_at,
                recycler_name=row.recycler_name,
                category=cat_val.capitalize(),
                quantity=p.purchased_quantity,
                amount=p.total_price,
                type=l.validity_risk or "Unknown",
                document_url=row.document_url
            )
        )
    return items

async def get_offline_deals(
    db: AsyncSession, company_id: uuid.UUID, offset: int = 0, limit: int = 10
) -> list[DashboardDealInvoiceItem]:
    query = (
        select(
            MaterialListing,
            Document.storage_key.label("document_url")
        )
        .outerjoin(Document, MaterialListing.invoice_document_id == Document.id)
        .where(MaterialListing.created_by_brand_id == company_id)
        .order_by(MaterialListing.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(query)
    rows = result.all()
    
    items = []
    for row in rows:
        l = row.MaterialListing
        cat_val = l.material_type.value if hasattr(l.material_type, "value") else str(l.material_type)
        items.append(
            DashboardDealInvoiceItem(
                invoice_no=str(l.id)[:8].upper(),
                date=l.created_at,
                recycler_name=l.offline_recycler_name or "Unknown",
                category=cat_val.capitalize(),
                quantity=l.total_quantity,
                amount=l.price_per_unit * l.total_quantity,
                type=l.validity_risk or "Unknown",
                document_url=row.document_url
            )
        )
    return items

async def get_wallet_transactions(
    db: AsyncSession, company_id: uuid.UUID, offset: int = 0, limit: int = 50
) -> list[WalletTransactionItem]:
    fetch_limit = offset + limit
    # Fetch Recharges
    recharge_query = (
        select(WalletRecharge)
        .where(WalletRecharge.company_id == company_id)
        .order_by(WalletRecharge.created_at.desc())
        .limit(fetch_limit)
    )
    recharge_result = await db.execute(recharge_query)
    recharges = recharge_result.scalars().all()

    # Fetch Purchases (deductions)
    purchase_query = (
        select(MaterialPurchase)
        .where(MaterialPurchase.brand_id == company_id)
        .order_by(MaterialPurchase.created_at.desc())
        .limit(fetch_limit)
    )
    purchase_result = await db.execute(purchase_query)
    purchases = purchase_result.scalars().all()

    transactions = []
    
    # Map recharges
    for r in recharges:
        status_val = r.status.value if hasattr(r.status, "value") else str(r.status)
        transactions.append({
            "transaction_id": str(r.id)[:8].upper(), # simple visual ID
            "date": r.created_at,
            "amount": r.amount,
            "is_credit": True,
            "payment_method": "Online",
            "type": "Wallet Recharge",
            "status": status_val.capitalize()
        })
        
    # Map purchases
    for p in purchases:
        # In UI, status is Success or Pending. 
        # For purchase, CONFIRMED/DELIVERED means Success, PENDING means Pending.
        status_val = p.purchase_status.value if hasattr(p.purchase_status, "value") else str(p.purchase_status)
        status = "Success" if p.purchase_status == PurchaseStatus.CONFIRMED else status_val.capitalize()
        transactions.append({
            "transaction_id": str(p.listing_id)[:8].upper(),
            "date": p.created_at,
            "amount": p.total_price,
            "is_credit": False,
            "payment_method": "Wallet",
            "type": "Purchase Payment",
            "status": status
        })
        
    # Sort by date descending
    transactions.sort(key=lambda x: x["date"], reverse=True)
    
    # Slice using offset and limit
    transactions = transactions[offset : offset + limit]
    
    return [WalletTransactionItem(**t) for t in transactions]


@router.get("/brand-dashboard", response_model=BrandDashboardKPIs)
async def get_brand_dashboard_kpis(
    company_id: uuid.UUID,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    purchase_history_offset: int = 0,
    purchase_history_limit: int = 10,
    wallet_history_offset: int = 0,
    wallet_history_limit: int = 10,
    top_recyclers_offset: int = 0,
    top_recyclers_limit: int = 5,
    deal_invoices_offset: int = 0,
    deal_invoices_limit: int = 10,
    offline_deals_offset: int = 0,
    offline_deals_limit: int = 10,
    admin_member: CompanyMember = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns aggregated lifetime KPIs for a brand.
    Restricted to Company Admins/Owners.
    """
    # 1. Get Company details
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company or company.company_type != CompanyType.BRAND:
        raise HTTPException(status_code=404, detail="Brand not found")

    # 2. Gather data
    breakdown_lifetime = await get_material_purchased_breakdown(db, company_id)
    breakdown_filtered = await get_material_purchased_breakdown(db, company_id, start_date, end_date)
    total_spend, avg_spend = await get_financials(db, company_id)
    epr_kpis = EPRKPIs(
        credits_available=company.epr_credits_available,
        credits_required=company.epr_credits_required,
    )
    unique_recyclers = await get_unique_recyclers_count(db, company_id)
    monthly_trend = await get_monthly_trend(db, company_id, start_date, end_date)
    top_recyclers = await get_top_recyclers(db, company_id, top_recyclers_offset, top_recyclers_limit)
    status_summary = await get_order_status_summary(db, company_id)
    recent_purchases = await get_recent_purchases(db, company_id, purchase_history_offset, purchase_history_limit)
    wallet_transactions = await get_wallet_transactions(db, company_id, wallet_history_offset, wallet_history_limit)
    deal_invoices = await get_deal_invoices(db, company_id, deal_invoices_offset, deal_invoices_limit)
    offline_deals = await get_offline_deals(db, company_id, offline_deals_offset, offline_deals_limit)

    # 3. Wallet summary
    recharge_result = await db.execute(
        select(func.sum(WalletRecharge.amount))
        .where(
            WalletRecharge.company_id == company_id,
            WalletRecharge.status == WalletRechargeStatus.SUCCESS.value
        )
    )
    total_recharge = recharge_result.scalar() or Decimal("0.00")
    
    wallet_kpis = WalletKPIs(
        current_balance=company.wallet_balance,
        pending_payments=company.frozen_wallet_balance,
        total_recharge=total_recharge,
        total_spending=total_spend
    )

    return BrandDashboardKPIs(
        company_id=company_id,
        material_purchased_breakdown=breakdown_lifetime,
        wallet_kpis=wallet_kpis,
        total_spend_inr=total_spend,
        avg_spend_per_mt=avg_spend,
        epr=epr_kpis,
        unique_recyclers_count=unique_recyclers,
        monthly_trend=monthly_trend,
        time_filtered_breakdown=breakdown_filtered,
        top_recyclers=top_recyclers,
        order_status_summary=status_summary,
        recent_purchases=recent_purchases,
        wallet_transactions=wallet_transactions,
        deal_invoices=deal_invoices,
        offline_deals=offline_deals,
    )
