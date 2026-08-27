import uuid
from decimal import Decimal
from datetime import datetime
import asyncio
from typing import Optional
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, literal, literal_column, union_all, Text, Numeric, case, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import (
    Company,
    CompanyType,
    CompanyMember,
    Document,
    DocumentStatus,
    MaterialListing,
    MaterialPurchase,
    CollectorPurchase,
    InvoiceProof,
    InvoiceProofCategory,
    PurchaseStatus,
    ArrivalStatus,
)
from app.schemas import (
    RecyclerDashboardKPIs,
    InvoiceStatsKPI,
    RecyclerMonthlySalesTrendItem,
    RecyclerDealStatusSummary,
    BrandDealBreakdownItem,
    CollectorDealBreakdownItem,
    CollectorPurchaseOut,
    CollectorSpendSummaryResponse,
    MonthlyCollectorSpendSummaryItem,
    CollectorSpendCategorySummaryItem,
    RecyclerFinancialReportResponse,
    RecyclerMonthlyReport,
    RecyclerMonthlyMaterialPurchased,
    RecyclerMonthlyMaterialRecycled,
    RecyclerWalletReview,
    RecyclerWalletInvoiceItem,
    InvoiceLedgerResponse,
    InvoiceLedgerItem,
    InvoiceProofCreate,
    InvoiceProofOut,
    InvoiceProofListResponse,
    UtilityMetricsKPIs,
)
from app.security import require_company_admin
from pydantic import BaseModel

class AttachDocumentRequest(BaseModel):
    document_id: uuid.UUID

router = APIRouter(prefix="/companies/{company_id}/kpis", tags=["kpis"])


@router.get("/recycler-dashboard", response_model=RecyclerDashboardKPIs)
async def get_recycler_dashboard_kpis(
    company_id: uuid.UUID,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    brand_deals_offset: int = Query(0, ge=0),
    brand_deals_limit: int = Query(10, gt=0, le=100),
    collector_deals_offset: int = Query(0, ge=0),
    collector_deals_limit: int = Query(10, gt=0, le=100),
    admin_member: CompanyMember = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns aggregated lifetime KPIs for a recycler.
    Restricted to Company Admins/Owners.
    """
    # 1. Verify Company
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company or company.company_type != CompanyType.RECYCLER:
        raise HTTPException(status_code=404, detail="Recycler not found")

    # 2. Monthly Sales Trend (filtered by dates if provided)
    trend_query = (
        select(
            func.date_trunc('month', MaterialPurchase.created_at).label("month"),
            func.sum(
                case(
                    (MaterialPurchase.purchase_status.in_([PurchaseStatus.CONFIRMED]), MaterialPurchase.total_price),
                    else_=0
                )
            ).label("amount_paid"),
            func.sum(
                case(
                    (MaterialPurchase.purchase_status == PurchaseStatus.PENDING, MaterialPurchase.total_price),
                    else_=0
                )
            ).label("amount_pending")
        )
        .join(MaterialListing, MaterialPurchase.listing_id == MaterialListing.id)
        .where(MaterialListing.recycler_id == company_id)
        .group_by(literal_column("1"))
        .order_by(literal_column("1"))
    )
    
    if start_date:
        trend_query = trend_query.where(MaterialPurchase.created_at >= start_date)
    if end_date:
        trend_query = trend_query.where(MaterialPurchase.created_at <= end_date)
        
    trend_result = await db.execute(trend_query)
    trend_rows = trend_result.all()
    
    monthly_sales_trend = []
    for row in trend_rows:
        if row.month:
            monthly_sales_trend.append(RecyclerMonthlySalesTrendItem(
                month=row.month.strftime('%Y-%m'),
                amount_paid=row.amount_paid or Decimal("0.00"),
                amount_pending=row.amount_pending or Decimal("0.00")
            ))

    # 3. Deal Status Summary (Lifetime)
    status_query = (
        select(
            func.sum(case((MaterialPurchase.purchase_status == PurchaseStatus.PENDING, 1), else_=0)).label("pending"),
            func.sum(case(((MaterialPurchase.purchase_status == PurchaseStatus.CONFIRMED) & (MaterialPurchase.arrival_status == ArrivalStatus.PENDING), 1), else_=0)).label("processing"),
            func.sum(case(((MaterialPurchase.purchase_status == PurchaseStatus.CONFIRMED) & (MaterialPurchase.arrival_status == ArrivalStatus.IN_TRANSIT), 1), else_=0)).label("in_transit"),
            func.sum(case(((MaterialPurchase.purchase_status == PurchaseStatus.CONFIRMED) & (MaterialPurchase.arrival_status == ArrivalStatus.DELIVERED), 1), else_=0)).label("delivered"),
            func.sum(case((MaterialPurchase.purchase_status == PurchaseStatus.CANCELLED, 1), else_=0)).label("cancelled")
        )
        .join(MaterialListing, MaterialPurchase.listing_id == MaterialListing.id)
        .where(MaterialListing.recycler_id == company_id)
    )
    status_result = await db.execute(status_query)
    status_row = status_result.one()
    
    deal_status_summary = RecyclerDealStatusSummary(
        pending=status_row.pending or 0,
        processing=status_row.processing or 0,
        in_transit=status_row.in_transit or 0,
        delivered=status_row.delivered or 0,
        cancelled=status_row.cancelled or 0
    )

    # 4. Brand Deals Breakdown
    brand_deals_base_query = (
        select(
            MaterialPurchase,
            Company.name.label("buyer_name"),
            Company.contact_person_name.label("buyer_contact_person"),
            Company.gst_number.label("buyer_gst_number"),
            Company.mobile_number.label("buyer_mobile_number"),
            Company.company_email.label("buyer_email"),
            Company.factory_address.label("buyer_address")
        )
        .join(MaterialListing, MaterialPurchase.listing_id == MaterialListing.id)
        .join(Company, MaterialPurchase.brand_id == Company.id)
        .where(MaterialListing.recycler_id == company_id)
        .order_by(MaterialPurchase.created_at.desc())
    )
    
    # Total count
    brand_deals_count_query = select(func.count()).select_from(brand_deals_base_query.subquery())
    total_brand_deals_count = (await db.execute(brand_deals_count_query)).scalar() or 0
    
    # Paginated results
    brand_deals_query = brand_deals_base_query.offset(brand_deals_offset).limit(brand_deals_limit)
    brand_deals_result = await db.execute(brand_deals_query)
    
    brand_deals_breakdown = []
    for row in brand_deals_result.all():
        p = row.MaterialPurchase
        # Determine human-readable status
        if p.purchase_status == PurchaseStatus.CANCELLED:
            status_str = "Cancelled"
        elif p.purchase_status == PurchaseStatus.PENDING:
            status_str = "Pending"
        else:
            if p.arrival_status == ArrivalStatus.PENDING:
                status_str = "Processing"
            elif p.arrival_status == ArrivalStatus.IN_TRANSIT:
                status_str = "In Transit"
            else:
                status_str = "Delivered"
                
        brand_deals_breakdown.append(BrandDealBreakdownItem(
            deal_id=str(p.id)[:8].upper(),
            buyer_name=row.buyer_name,
            buyer_contact_person=row.buyer_contact_person,
            buyer_gst_number=row.buyer_gst_number,
            buyer_mobile_number=row.buyer_mobile_number,
            buyer_email=row.buyer_email,
            buyer_address=row.buyer_address,
            date_of_deal=p.created_at,
            quantity=p.purchased_quantity,
            amount=p.total_price,
            status=status_str,
            invoice_url=f"/companies/{company_id}/kpis/brand-deals/{p.id}/invoice"
        ))

    # 5. Collector Deals Breakdown
    collector_base_query = (
        select(CollectorPurchase, Document.storage_key.label("document_url"))
        .outerjoin(Document, CollectorPurchase.document_id == Document.id)
        .where(CollectorPurchase.recycler_id == company_id)
        .order_by(CollectorPurchase.created_at.desc())
    )
    
    # Total count
    collector_count_query = select(func.count()).select_from(collector_base_query.subquery())
    total_collector_deals_count = (await db.execute(collector_count_query)).scalar() or 0
    
    # Total spend
    collector_spend_query = select(func.sum(CollectorPurchase.price)).where(CollectorPurchase.recycler_id == company_id)
    total_collector_spend = (await db.execute(collector_spend_query)).scalar() or Decimal("0.00")
    
    # Paginated results
    collector_deals_query = collector_base_query.offset(collector_deals_offset).limit(collector_deals_limit)
    collector_deals_result = await db.execute(collector_deals_query)
    
    collector_deals_breakdown = []
    for row in collector_deals_result.all():
        cp = row.CollectorPurchase
        collector_deals_breakdown.append(CollectorDealBreakdownItem(
            id=cp.id,
            collector_name=cp.collector_name,
            material_type=cp.material_type,
            quantity=cp.quantity,
            price=cp.price,
            document_url=row.document_url,
            created_at=cp.created_at
        ))

    return RecyclerDashboardKPIs(
        company_id=company_id,
        monthly_sales_trend=monthly_sales_trend,
        deal_status_summary=deal_status_summary,
        brand_deals_breakdown=brand_deals_breakdown,
        total_brand_deals_count=total_brand_deals_count,
        collector_deals_breakdown=collector_deals_breakdown,
        total_collector_deals_count=total_collector_deals_count,
        total_collector_spend=total_collector_spend
    )


@router.get("/collector-spend-summary", response_model=CollectorSpendSummaryResponse)
async def get_collector_spend_summary(
    company_id: uuid.UUID,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    admin_member: CompanyMember = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns standalone month-wise collector spend aggregation broken down by category and material type.
    """
    # Verify Company
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company or company.company_type != CompanyType.RECYCLER:
        raise HTTPException(status_code=404, detail="Recycler not found")

    query = (
        select(
            func.date_trunc('month', CollectorPurchase.created_at).label("month"),
            CollectorPurchase.category,
            CollectorPurchase.material_type,
            func.sum(CollectorPurchase.price).label("total_spend"),
            func.sum(CollectorPurchase.quantity).label("total_quantity")
        )
        .where(CollectorPurchase.recycler_id == company_id)
        .group_by(
            literal_column("1"),
            CollectorPurchase.category,
            CollectorPurchase.material_type
        )
        .order_by(literal_column("1 DESC"))
    )
    
    if start_date:
        query = query.where(CollectorPurchase.created_at >= start_date)
    if end_date:
        query = query.where(CollectorPurchase.created_at <= end_date)
        
    result = await db.execute(query)
    rows = result.all()
    
    # Aggregate into month buckets
    monthly_data = {}
    for row in rows:
        if not row.month:
            continue
            
        month_str = row.month.strftime('%Y-%m')
        if month_str not in monthly_data:
            monthly_data[month_str] = {
                "total_spend": Decimal("0.00"),
                "breakdown": []
            }
            
        spend = row.total_spend or Decimal("0.00")
        qty = row.total_quantity or Decimal("0.00")
        
        monthly_data[month_str]["total_spend"] += spend
        
        cat_val = row.category.value if hasattr(row.category, "value") else str(row.category)
        
        monthly_data[month_str]["breakdown"].append(CollectorSpendCategorySummaryItem(
            category=cat_val,
            material_type=row.material_type,
            total_spend=spend,
            total_quantity=qty
        ))
        
    monthly_summaries = []
    for m_str, data in monthly_data.items():
        monthly_summaries.append(MonthlyCollectorSpendSummaryItem(
            month=m_str,
            total_spend=data["total_spend"],
            breakdown=data["breakdown"]
        ))
        
    # Sort months descending
    monthly_summaries.sort(key=lambda x: x.month, reverse=True)

    return CollectorSpendSummaryResponse(monthly_summaries=monthly_summaries)


@router.patch("/collector-purchases/{purchase_id}/document", response_model=CollectorPurchaseOut)
async def attach_document_to_collector_purchase(
    company_id: uuid.UUID,
    purchase_id: uuid.UUID,
    body: AttachDocumentRequest,
    admin_member: CompanyMember = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Attaches an uploaded document to a specific collector purchase.
    """
    # 1. Verify purchase belongs to company
    purchase = (await db.execute(
        select(CollectorPurchase).where(
            CollectorPurchase.id == purchase_id,
            CollectorPurchase.recycler_id == company_id
        ).with_for_update()
    )).scalar_one_or_none()
    
    if not purchase:
        raise HTTPException(status_code=404, detail="Collector purchase not found")
        
    # 2. Verify document belongs to company
    doc = (await db.execute(
        select(Document).where(
            Document.id == body.document_id,
            Document.company_id == company_id
        )
    )).scalar_one_or_none()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found or access denied")
        
    purchase.document_id = doc.id
    await db.commit()
    await db.refresh(purchase)
    
    return purchase


@router.get("/invoice-stats", response_model=InvoiceStatsKPI)
async def get_recycler_invoice_stats(
    company_id: uuid.UUID,
    admin_member: CompanyMember = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns statistics about all documents (invoices) uploaded by the recycler.
    """
    stats_query = (
        select(Document.status, func.count())
        .where(Document.company_id == company_id)
        .group_by(Document.status)
    )
    res = await db.execute(stats_query)
    
    total = 0
    approved = 0
    pending = 0
    rejected = 0
    
    for status, count in res.all():
        total += count
        if status == DocumentStatus.VERIFIED:
            approved += count
        elif status == DocumentStatus.PENDING_VERIFICATION:
            pending += count
        elif status == DocumentStatus.REJECTED:
            rejected += count
            
    return InvoiceStatsKPI(
        total_uploaded=total,
        approved=approved,
        pending=pending,
        rejected=rejected
    )


@router.get("/wallet-review", response_model=RecyclerWalletReview)
async def get_recycler_wallet_review(
    company_id: uuid.UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0, le=100),
    admin_member: CompanyMember = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns wallet metrics (received vs pending) and paginated invoice lists for Brand deals.
    """
    # 1. Get totals
    totals_query = select(
        func.sum(MaterialPurchase.total_price).filter(MaterialPurchase.purchase_status == PurchaseStatus.CONFIRMED).label("paid"),
        func.sum(MaterialPurchase.total_price).filter(MaterialPurchase.purchase_status == PurchaseStatus.PENDING).label("pending"),
        func.count(MaterialPurchase.id).label("total_count")
    ).select_from(
        MaterialPurchase
    ).join(
        MaterialListing, MaterialPurchase.listing_id == MaterialListing.id
    ).where(
        MaterialListing.recycler_id == company_id
    )

    totals_res = (await db.execute(totals_query)).one()
    
    total_paid = totals_res.paid or Decimal("0.00")
    total_pending = totals_res.pending or Decimal("0.00")
    total_count = totals_res.total_count or 0

    # 2. Get paginated invoices
    base_query = (
        select(MaterialPurchase, Company)
        .join(MaterialListing, MaterialPurchase.listing_id == MaterialListing.id)
        .join(Company, MaterialPurchase.brand_id == Company.id)
        .where(MaterialListing.recycler_id == company_id)
    )
    invoices_query = base_query.order_by(MaterialPurchase.created_at.desc()).offset(offset).limit(limit)
    invoices_res = await db.execute(invoices_query)

    invoices = []
    for p, company in invoices_res.all():
        if p.purchase_status == PurchaseStatus.CANCELLED:
            status_str = "Cancelled"
        elif p.purchase_status == PurchaseStatus.PENDING:
            status_str = "Pending"
        else:
            if p.arrival_status == ArrivalStatus.PENDING:
                status_str = "Processing"
            elif p.arrival_status == ArrivalStatus.IN_TRANSIT:
                status_str = "In Transit"
            else:
                status_str = "Delivered"

        invoices.append(RecyclerWalletInvoiceItem(
            invoice_no=str(p.id)[:8].upper(),
            company_name=company.name,
            amount=p.total_price,
            date_of_deal=p.created_at,
            status=status_str,
            invoice_url=f"/companies/{company_id}/kpis/brand-deals/{p.id}/invoice"
        ))

    return RecyclerWalletReview(
        total_payment_received=total_paid,
        total_pending_amount=total_pending,
        total_invoices_count=total_count,
        invoices=invoices
    )


@router.get("/invoice-ledger", response_model=InvoiceLedgerResponse)
async def get_recycler_invoice_ledger(
    company_id: uuid.UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0, le=100),
    admin_member: CompanyMember = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns a unified ledger of both incoming collector invoices (purchases) 
    and outgoing brand invoices (sales).
    """
    # 1. Sales to Brands (MaterialPurchase)
    q1 = select(
        MaterialPurchase.id.cast(Text).label("id"),
        MaterialPurchase.created_at.label("created_at"),
        Company.name.label("supplier"),
        MaterialListing.material_type.cast(Text).label("category"),
        MaterialPurchase.purchased_quantity.label("qty"),
        case(
            (MaterialPurchase.purchased_quantity == 0, literal(0, type_=Numeric)),
            else_=(MaterialPurchase.total_price / MaterialPurchase.purchased_quantity * 1000).cast(Numeric)
        ).label("rate"),
        MaterialPurchase.total_price.label("total"),
        literal("SALE", type_=Text).label("deal_type"),
        literal(None, type_=Text).label("document_id")
    ).select_from(MaterialPurchase).join(
        MaterialListing, MaterialPurchase.listing_id == MaterialListing.id
    ).join(
        Company, MaterialPurchase.brand_id == Company.id
    ).where(
        MaterialListing.recycler_id == company_id,
        MaterialPurchase.purchase_status == PurchaseStatus.CONFIRMED
    )

    # 2. Purchases from Collectors (CollectorPurchase)
    q2 = select(
        CollectorPurchase.id.cast(Text).label("id"),
        CollectorPurchase.created_at.label("created_at"),
        CollectorPurchase.collector_company_name.label("supplier"),
        CollectorPurchase.category.cast(Text).label("category"),
        CollectorPurchase.quantity.label("qty"),
        case(
            (CollectorPurchase.quantity == 0, literal(0, type_=Numeric)),
            else_=(CollectorPurchase.price / CollectorPurchase.quantity * 1000).cast(Numeric)
        ).label("rate"),
        CollectorPurchase.price.label("total"),
        literal("PURCHASE", type_=Text).label("deal_type"),
        func.coalesce(Document.id.cast(Text), literal("", type_=Text)).label("document_id")
    ).select_from(CollectorPurchase).outerjoin(
        Document, CollectorPurchase.document_id == Document.id
    ).where(CollectorPurchase.recycler_id == company_id)

    union_subq = union_all(q1, q2).subquery()
    
    # Get total count
    count_query = select(func.count()).select_from(union_subq)
    total_count = (await db.execute(count_query)).scalar() or 0

    # Get paginated data (Deterministic Sort)
    data_query = select(union_subq).order_by(
        union_subq.c.created_at.desc(),
        union_subq.c.id.asc()
    ).offset(offset).limit(limit)
    res = await db.execute(data_query)
    
    items = []
    for row in res.all():
        deal_id_str = str(row.id)
        short_id = deal_id_str[:8].upper()
        
        if row.deal_type == "SALE":
            action_url = f"/companies/{company_id}/kpis/brand-deals/{deal_id_str}/invoice"
        else:
            action_url = f"/companies/{company_id}/documents/{row.document_id}/download" if row.document_id else None
            
        items.append(InvoiceLedgerItem(
            invoice_no=short_id,
            date=row.created_at,
            supplier=row.supplier,
            category=row.category,
            qty=row.qty,
            rate=row.rate,
            total=row.total,
            action_url=action_url,
            deal_type=row.deal_type
        ))
        
    return InvoiceLedgerResponse(
        items=items,
        total_count=total_count
    )


@router.get("/financial-report", response_model=RecyclerFinancialReportResponse)
async def get_recycler_financial_report(
    company_id: uuid.UUID,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    admin_member: CompanyMember = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns a comprehensive financial and material report for the recycler,
    broken down by month.
    """
    # 1. Collector Purchases Query (Spend)
    cp_query = (
        select(
            func.to_char(CollectorPurchase.created_at, 'YYYY-MM').label("month"),
            CollectorPurchase.category,
            CollectorPurchase.material_type,
            func.sum(CollectorPurchase.quantity).label("total_quantity"),
            func.sum(CollectorPurchase.price).label("total_spend"),
        )
        .where(CollectorPurchase.recycler_id == company_id)
    )
    if start_date:
        cp_query = cp_query.where(CollectorPurchase.created_at >= start_date)
    if end_date:
        cp_query = cp_query.where(CollectorPurchase.created_at <= end_date)
    
    cp_query = cp_query.group_by(
        literal_column("1"),
        CollectorPurchase.category,
        CollectorPurchase.material_type
    )

    # 2. Material Recycled Query (Listings)
    ml_query = (
        select(
            func.to_char(MaterialListing.created_at, 'YYYY-MM').label("month"),
            MaterialListing.category,
            MaterialListing.material_type,
            func.sum(MaterialListing.total_quantity).label("total_quantity"),
        )
        .where(MaterialListing.recycler_id == company_id)
    )
    if start_date:
        ml_query = ml_query.where(MaterialListing.created_at >= start_date)
    if end_date:
        ml_query = ml_query.where(MaterialListing.created_at <= end_date)
    
    ml_query = ml_query.group_by(
        literal_column("1"),
        MaterialListing.category,
        MaterialListing.material_type
    )

    # 3. Brand Sales Query (Revenue)
    # Join MaterialPurchase -> MaterialListing
    mp_query = (
        select(
            func.to_char(MaterialPurchase.created_at, 'YYYY-MM').label("month"),
            MaterialPurchase.purchase_status,
            func.sum(MaterialPurchase.total_price).label("total_price"),
        )
        .join(MaterialListing, MaterialPurchase.listing_id == MaterialListing.id)
        .where(MaterialListing.recycler_id == company_id)
    )
    if start_date:
        mp_query = mp_query.where(MaterialPurchase.created_at >= start_date)
    if end_date:
        mp_query = mp_query.where(MaterialPurchase.created_at <= end_date)
    
    mp_query = mp_query.group_by(
        literal_column("1"),
        MaterialPurchase.purchase_status
    )

    # Execute all concurrently
    cp_res, ml_res, mp_res = await asyncio.gather(
        db.execute(cp_query),
        db.execute(ml_query),
        db.execute(mp_query)
    )

    months_data = defaultdict(lambda: {
        "material_purchased_from_collectors": [],
        "material_recycled": [],
        "sales_paid": Decimal("0.00"),
        "sales_pending": Decimal("0.00"),
        "total_spend": Decimal("0.00")
    })

    # Process Collector Purchases
    for row in cp_res.all():
        months_data[row.month]["material_purchased_from_collectors"].append(
            RecyclerMonthlyMaterialPurchased(
                category=row.category.value if hasattr(row.category, "value") else str(row.category),
                material_type=row.material_type,
                total_quantity=row.total_quantity or Decimal("0"),
                total_spend=row.total_spend or Decimal("0")
            )
        )
        months_data[row.month]["total_spend"] += row.total_spend or Decimal("0")

    # Process Material Recycled
    for row in ml_res.all():
        months_data[row.month]["material_recycled"].append(
            RecyclerMonthlyMaterialRecycled(
                category=row.category.value if hasattr(row.category, "value") else str(row.category),
                material_type=row.material_type,
                total_quantity=row.total_quantity or Decimal("0")
            )
        )

    # Process Brand Sales
    for row in mp_res.all():
        if row.purchase_status == PurchaseStatus.CONFIRMED:
            months_data[row.month]["sales_paid"] += row.total_price or Decimal("0")
        elif row.purchase_status == PurchaseStatus.PENDING:
            months_data[row.month]["sales_pending"] += row.total_price or Decimal("0")

    # Compile the final result
    monthly_reports = []
    
    total_sales_paid = Decimal("0.00")
    total_sales_pending = Decimal("0.00")
    total_spend = Decimal("0.00")
    total_material_recycled = Decimal("0.00")

    for month, data in sorted(months_data.items(), reverse=True):
        revenue = data["sales_paid"] - data["total_spend"]
        
        # Calculate material recycled sum for this month
        month_recycled_sum = sum(x.total_quantity for x in data["material_recycled"])
        
        monthly_reports.append(RecyclerMonthlyReport(
            month=month,
            material_purchased_from_collectors=data["material_purchased_from_collectors"],
            material_recycled=data["material_recycled"],
            sales_paid=data["sales_paid"],
            sales_pending=data["sales_pending"],
            revenue=revenue
        ))
        
        total_sales_paid += data["sales_paid"]
        total_sales_pending += data["sales_pending"]
        total_spend += data["total_spend"]
        total_material_recycled += month_recycled_sum

    total_sales_period = total_sales_paid + total_sales_pending
    total_revenue_period = total_sales_paid - total_spend

    return RecyclerFinancialReportResponse(
        total_revenue_period=total_revenue_period,
        total_sales_period=total_sales_period,
        total_sales_paid=total_sales_paid,
        total_sales_pending=total_sales_pending,
        total_material_recycled=total_material_recycled,
        monthly_reports=monthly_reports
    )


# ============================================================================
# Invoice Proofs & Utility Metrics
# ============================================================================
@router.post("/invoice-proofs", response_model=InvoiceProofOut)
async def create_invoice_proof(
    company_id: uuid.UUID,
    payload: InvoiceProofCreate,
    admin_member: CompanyMember = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a new proof bill tied to a specific collector purchase.
    """
    # Verify the collector purchase exists and belongs to this recycler
    purchase = await db.get(CollectorPurchase, payload.invoice_id)
    if not purchase or purchase.recycler_id != company_id:
        raise HTTPException(status_code=404, detail="Collector Purchase not found")

    # Prevent duplicate proof for the same (collector purchase, category) pair
    existing_proof = (await db.execute(
        select(InvoiceProof).where(
            InvoiceProof.invoice_id == payload.invoice_id,
            InvoiceProof.recycler_id == company_id,
            InvoiceProof.category == payload.category
        )
    )).scalar_one_or_none()
    if existing_proof:
        raise HTTPException(status_code=409, detail="An invoice proof for this category already exists for this collector purchase")

    if payload.document_id:
        doc = await db.get(Document, payload.document_id)
        if not doc or doc.company_id != company_id:
            raise HTTPException(status_code=403, detail="Document not found or unauthorized")
        
    new_proof = InvoiceProof(
        recycler_id=company_id,
        invoice_id=payload.invoice_id,
        document_name=payload.document_name,
        category=payload.category,
        period=payload.period,
        unit_consumed=payload.unit_consumed,
        amount_spent=payload.amount_spent,
        total_amount_used=payload.total_amount_used,
        total_amount_recycled=payload.total_amount_recycled,
        document_id=payload.document_id,
    )
    db.add(new_proof)
    await db.commit()
    await db.refresh(new_proof)
    
    return new_proof


@router.get("/invoice-proofs", response_model=InvoiceProofListResponse)
async def list_invoice_proofs(
    company_id: uuid.UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0, le=100),
    admin_member: CompanyMember = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    List all uploaded invoice proofs for the recycler, with pagination and download links.
    """
    # Base query joining Document to get storage_key (document_url)
    base_query = (
        select(InvoiceProof, Document.storage_key.label("document_url"))
        .outerjoin(Document, InvoiceProof.document_id == Document.id)
        .where(InvoiceProof.recycler_id == company_id)
    )
    
    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    total_count = (await db.execute(count_query)).scalar() or 0

    # Get paginated data
    data_query = base_query.order_by(InvoiceProof.created_at.desc()).offset(offset).limit(limit)
    res = await db.execute(data_query)
    
    items = []
    for row in res.all():
        proof = row.InvoiceProof
        items.append(InvoiceProofOut(
            id=proof.id,
            invoice_id=proof.invoice_id,
            document_name=proof.document_name,
            category=proof.category,
            period=proof.period,
            unit_consumed=proof.unit_consumed,
            amount_spent=proof.amount_spent,
            total_amount_used=proof.total_amount_used,
            total_amount_recycled=proof.total_amount_recycled,
            document_id=proof.document_id,
            document_url=row.document_url,
            created_at=proof.created_at
        ))

    return InvoiceProofListResponse(
        items=items,
        total_count=total_count
    )


@router.get("/utility-metrics", response_model=UtilityMetricsKPIs)
async def get_utility_metrics_kpis(
    company_id: uuid.UUID,
    admin_member: CompanyMember = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the 4 Utility KPIs:
    1. Energy / Output Ratio (kWh/MT)
    2. Waybill Verified Scrap (MT)
    3. Recorded Utility Invoices (Total amount spent)
    4. Verified Proof Files (Total count)
    """
    # KPI 1: Energy / Output Ratio
    # Sum of unit_consumed for ELECTRICITY / Sum of total_amount_recycled
    energy_q = select(
        func.coalesce(func.sum(InvoiceProof.unit_consumed), 0),
        func.coalesce(func.sum(InvoiceProof.total_amount_recycled), 0)
    ).where(
        InvoiceProof.recycler_id == company_id,
        InvoiceProof.category == InvoiceProofCategory.ELECTRICITY
    )
    energy_res = (await db.execute(energy_q)).first()
    total_kwh = energy_res[0] if energy_res else Decimal("0")
    total_recycled = energy_res[1] if energy_res else Decimal("0")
    
    energy_output_ratio = Decimal("0.00")
    if total_recycled > 0:
        energy_output_ratio = total_kwh / total_recycled

    # KPI 2: Waybill Verified Scrap
    # Sum of total_amount_used for LOGISTICS
    logistics_q = select(func.coalesce(func.sum(InvoiceProof.total_amount_used), 0)).where(
        InvoiceProof.recycler_id == company_id,
        InvoiceProof.category == InvoiceProofCategory.LOGISTICS
    )
    waybill_verified_scrap = (await db.execute(logistics_q)).scalar() or Decimal("0.00")

    # KPI 3: Recorded Utility Invoices (Cost)
    # Sum of amount_spent across ALL categories
    cost_q = select(func.coalesce(func.sum(InvoiceProof.amount_spent), 0)).where(
        InvoiceProof.recycler_id == company_id
    )
    recorded_utility_invoices = (await db.execute(cost_q)).scalar() or Decimal("0.00")

    # KPI 4: Verified Proof Files
    # Count of ALL invoice proof rows where the associated document is VERIFIED
    count_q = select(func.count()).select_from(InvoiceProof).join(
        Document, InvoiceProof.document_id == Document.id
    ).where(
        InvoiceProof.recycler_id == company_id,
        Document.status == DocumentStatus.VERIFIED
    )
    verified_proof_files = (await db.execute(count_q)).scalar() or 0

    return UtilityMetricsKPIs(
        energy_output_ratio=energy_output_ratio,
        waybill_verified_scrap=waybill_verified_scrap,
        recorded_utility_invoices=recorded_utility_invoices,
        verified_proof_files=verified_proof_files
    )
