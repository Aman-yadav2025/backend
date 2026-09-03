"""
Brand Marketplace router
========================
Endpoints for Brands to browse recycler listings and make purchases.

Purchase flow (50/50 wallet split with full upfront freeze):
  1. Brand calls POST /{listing_id}/purchase with a quantity.
  2. Server validates: available_balance (wallet - frozen) >= total_price.
  3. 50% (immediate_deduction) is deducted from wallet_balance NOW.
  4. 50% (pending_deduction) is added to frozen_wallet_balance (ring-fenced).
  5. listing.available_quantity is decremented (inventory reserved).
  6. MaterialPurchase is created with purchase_status=PENDING.

On delivery confirmation (POST /purchases/{id}/confirm-delivery):
  - wallet_balance  -= pending_wallet_deduction  (settle second half)
  - frozen_wallet_balance -= pending_wallet_deduction  (unfreeze)
  - purchase_status = CONFIRMED, arrival_status = DELIVERED

On cancellation (POST /purchases/{id}/cancel, only while PENDING):
  - wallet_balance  += immediate_deduction  (refund first half)
  - frozen_wallet_balance -= pending_deduction  (unfreeze second half)
  - listing.available_quantity += purchased_quantity  (release inventory)
  - purchase_status = CANCELLED

Endpoint summary:
  GET    /companies/{company_id}/marketplace                           — Browse active listings
  GET    /companies/{company_id}/marketplace/{listing_id}              — Single listing detail
  POST   /companies/{company_id}/marketplace/{listing_id}/purchase     — Buy from a listing
  GET    /companies/{company_id}/marketplace/purchases                 — List brand's purchases
  POST   /companies/{company_id}/marketplace/purchases/{id}/confirm-delivery — Confirm delivery
  POST   /companies/{company_id}/marketplace/purchases/{id}/cancel     — Cancel purchase
"""

import uuid
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import cast, case, func, select, text, Numeric
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import array

from app.database import get_db
from app.models import (
    Company,
    CompanyMember,
    CompanyType,
    MaterialListing,
    MaterialPurchase,
    MaterialType,
    PurchaseStatus,
    ArrivalStatus,
    PaymentMethod,
    Document,
)
from app.services import razorpay_client
from app.services.r2_storage import generate_presigned_download_url
from app.schemas import (
    BrandPurchasedFromFilter,
    BrandPurchaseFilter,
    MarketplaceSearchFilter,
    MaterialListingOut,
    MaterialPurchaseCreate,
    MaterialPurchaseOut,
    OfflineDealCreate,
    RecyclerProfileOut,
)
from app.security import require_company_admin, require_active_company_membership

router = APIRouter(prefix="/companies/{company_id}/marketplace", tags=["brand-marketplace"])


@router.post("/offline-deals", response_model=MaterialListingOut, status_code=status.HTTP_201_CREATED)
async def create_offline_deal(
    company_id: uuid.UUID,
    payload: OfflineDealCreate,
    admin_member: CompanyMember = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Creates an offline deal manually recorded by a Brand.
    This creates a MaterialListing with available_quantity = 0.
    """
    # Verify the company is a Brand
    company_result = await db.execute(select(Company).where(Company.id == company_id))
    company = company_result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    if company.company_type != CompanyType.BRAND:
        raise HTTPException(status_code=403, detail="Only Brands can record offline deals")

    price_per_unit = payload.total_price / payload.quantity

    new_listing = MaterialListing(
        recycler_id=None,
        created_by_brand_id=company_id,
        offline_recycler_name=f"{payload.recycler_name} (from {company.name})",
        material_type=payload.material_type,
        category=payload.category,
        grade=payload.grade,
        price_per_unit=price_per_unit,
        total_quantity=payload.quantity,
        available_quantity=Decimal("0.00"),
        validity_risk=payload.validity_risk,
        invoice_document_id=payload.invoice_document_id,
    )
    db.add(new_listing)
    await db.commit()
    await db.refresh(new_listing)

    return new_listing


# ─── Shared dependency: verify BRAND company ─────────────────────────────────

async def _require_brand(
    company_id: uuid.UUID,
    _member: CompanyMember = Depends(require_active_company_membership),
    db: AsyncSession = Depends(get_db),
) -> tuple[Company, CompanyMember]:
    """
    Verifies the caller is an active member of the company AND that the
    company is a BRAND. Returns (company, membership) without locking —
    individual endpoints lock what they need.
    """
    company = await db.scalar(
        select(Company).where(
            Company.id == company_id,
            Company.deleted_at.is_(None),
        )
    )
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    if company.company_type != CompanyType.BRAND:
        raise HTTPException(
            status_code=403,
            detail="Only BRAND companies can access the marketplace",
        )
    return company, _member


async def _require_brand_admin(
    company_id: uuid.UUID,
    _admin: CompanyMember = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
) -> tuple[Company, CompanyMember]:
    """Like _require_brand but requires OWNER-level membership."""
    company = await db.scalar(
        select(Company).where(
            Company.id == company_id,
            Company.deleted_at.is_(None),
        )
    )
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    if company.company_type != CompanyType.BRAND:
        raise HTTPException(
            status_code=403,
            detail="Only BRAND companies can access the marketplace",
        )
    return company, _admin


# ─── Browse listings (Advanced Search) ───────────────────────────────────────

@router.get("", response_model=list[MaterialListingOut])
async def browse_listings(
    company_id: uuid.UUID,
    # ── Material & Category ───────────────────────────────────────────────────
    material_type: Optional[str] = Query(default=None, description="Exact match: PLASTIC, METAL, or BOTH."),
    category: Optional[str] = Query(default=None, description="Substring (case-insensitive) search on category."),
    grade: Optional[str] = Query(default=None, description="Substring (case-insensitive) search on grade."),
    # ── Purity (JSONB) ────────────────────────────────────────────────────────
    min_purity: Optional[Decimal] = Query(default=None, ge=0, le=100, description="Min purity % from technical_parameters."),
    max_purity: Optional[Decimal] = Query(default=None, ge=0, le=100, description="Max purity % from technical_parameters."),
    # ── Price ─────────────────────────────────────────────────────────────────
    min_price: Optional[Decimal] = Query(default=None, ge=0, description="Minimum price per unit (₹)."),
    max_price: Optional[Decimal] = Query(default=None, ge=0, description="Maximum price per unit (₹)."),
    # ── Volume & Availability ──────────────────────────────────────────────────
    min_quantity: Optional[Decimal] = Query(default=None, ge=0, description="Minimum available quantity."),
    sold_out: Optional[bool] = Query(default=None, description="True=Sold out, False=Remaining inventory"),
    # ── Certifications ────────────────────────────────────────────────────────
    certifications: Optional[list[str]] = Query(default=None, description="Required certifications (ALL must match)."),
    # ── Recycler / Location ───────────────────────────────────────────────────
    recycler_id: Optional[uuid.UUID] = Query(default=None, description="Filter to a specific recycler."),
    state: Optional[str] = Query(default=None, description="Substring search on recycler state."),
    city: Optional[str] = Query(default=None, description="Substring search on recycler city."),
    min_esg_rating: Optional[int] = Query(default=None, ge=0, le=100, description="Minimum recycler ESG rating."),
    # ── Sorting & Pagination ──────────────────────────────────────────────────
    sort_by: Literal["price_asc", "price_desc", "carbon_desc", "date_desc", "recommended"] = Query(default="date_desc", description="Sorting strategy."),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    deps: tuple[Company, CompanyMember] = Depends(_require_brand),
    db: AsyncSession = Depends(get_db),
):
    """
    Advanced search for all active recycler listings visible to this Brand.
    All filters are optional and fully combinable.

    **sort_by='recommended'** ranks listings that can best fulfill the brand's
    remaining EPR credit deficit (epr_credits_required - epr_credits_purchased)
    — listings that can single-handedly cover the gap appear first.
    """
    brand_company, _ = deps

    q = select(
        MaterialListing,
        Company.name.label("recycler_name"),
        Company.city.label("recycler_city"),
        Company.state.label("recycler_state"),
    ).outerjoin(Company, MaterialListing.recycler_id == Company.id).where(
        MaterialListing.is_active.is_(True),
        MaterialListing.created_by_brand_id.is_(None),
        Company.deleted_at.is_(None),
    )

    # ── Apply filters ──────────────────────────────────────────────────────────
    if material_type is not None:
        q = q.where(MaterialListing.material_type == material_type)
    if category is not None:
        q = q.where(MaterialListing.category.ilike(f"%{category}%"))
    if grade is not None:
        q = q.where(MaterialListing.grade.ilike(f"%{grade}%"))
    if min_price is not None:
        q = q.where(MaterialListing.price_per_unit >= min_price)
    if max_price is not None:
        q = q.where(MaterialListing.price_per_unit <= max_price)
    if min_quantity is not None:
        q = q.where(MaterialListing.available_quantity >= min_quantity)
    if sold_out is True:
        q = q.where(MaterialListing.available_quantity == 0)
    elif sold_out is False:
        q = q.where(MaterialListing.available_quantity > 0)
    if recycler_id is not None:
        q = q.where(MaterialListing.recycler_id == recycler_id)
    if state is not None:
        q = q.where(Company.state.ilike(f"%{state}%"))
    if city is not None:
        q = q.where(Company.city.ilike(f"%{city}%"))
    if min_esg_rating is not None:
        q = q.where(Company.esg_rating >= min_esg_rating)

    # Purity: cast the JSONB text value to NUMERIC for comparison.
    # Rows where technical_parameters is NULL or the key is absent will have
    # a NULL cast result, causing them to be excluded — the correct behaviour.
    if min_purity is not None:
        q = q.where(
            cast(MaterialListing.technical_parameters["purity"].as_string(), Numeric)
            >= min_purity
        )
    if max_purity is not None:
        q = q.where(
            cast(MaterialListing.technical_parameters["purity"].as_string(), Numeric)
            <= max_purity
        )

    # Certifications: listing must contain ALL requested certs
    if certifications:
        cert_array = array(certifications)
        q = q.where(MaterialListing.accreditations.contains(cert_array))

    # ── Apply sorting ──────────────────────────────────────────────────────────
    if sort_by == "price_asc":
        q = q.order_by(MaterialListing.price_per_unit.asc())
    elif sort_by == "price_desc":
        q = q.order_by(MaterialListing.price_per_unit.desc())
    elif sort_by == "carbon_desc":
        q = q.order_by(MaterialListing.carbon_reduction_per_kg.desc().nulls_last())
    elif sort_by == "recommended":
        # Remaining EPR credits the brand still needs to fulfill
        remaining = brand_company.epr_credits_required - brand_company.epr_credits_purchased
        if remaining <= 0:
            # No deficit — fall back to newest first
            q = q.order_by(MaterialListing.created_at.desc())
        else:
            # 0 = can fulfill the gap entirely (best), 1 = cannot (goes last)
            can_fulfill = case(
                (MaterialListing.available_quantity >= remaining, 0),
                else_=1,
            )
            # Among those that CAN fulfill: smallest surplus first
            # Among those that CANNOT: largest quantity first (maximises partial coverage)
            proximity = func.abs(MaterialListing.available_quantity - remaining)
            q = q.order_by(can_fulfill.asc(), proximity.asc())
    else:  # default: date_desc
        q = q.order_by(MaterialListing.created_at.desc())

    q = q.limit(limit).offset(offset)

    result = await db.execute(q)
    rows = result.all()

    out_list = []
    for row in rows:
        out = MaterialListingOut.model_validate(row.MaterialListing)
        out.recycler_name = row.recycler_name
        out.recycler_city = row.recycler_city
        out.recycler_state = row.recycler_state
        out_list.append(out)

    return out_list


@router.get("/recyclers/{recycler_id}", response_model=RecyclerProfileOut)
async def get_recycler_profile(
    company_id: uuid.UUID,
    recycler_id: uuid.UUID,
    deps: tuple[Company, CompanyMember] = Depends(_require_brand),
    db: AsyncSession = Depends(get_db),
):
    """Returns the public profile data of a Recycler partner."""
    q = select(Company).where(
        Company.id == recycler_id,
        Company.company_type == CompanyType.RECYCLER,
        Company.deleted_at.is_(None)
    )
    result = await db.execute(q)
    recycler = result.scalar_one_or_none()
    
    if recycler is None:
        raise HTTPException(status_code=404, detail="Recycler not found or unavailable")
        
    return RecyclerProfileOut.model_validate(recycler)


@router.get("/{listing_id}", response_model=MaterialListingOut)
async def get_listing_detail(
    company_id: uuid.UUID,
    listing_id: uuid.UUID,
    deps: tuple[Company, CompanyMember] = Depends(_require_brand),
    db: AsyncSession = Depends(get_db),
):
    """Returns a single active listing detail."""
    q = select(
        MaterialListing,
        Company.name.label("recycler_name"),
        Company.city.label("recycler_city"),
        Company.state.label("recycler_state")
    ).outerjoin(Company, MaterialListing.recycler_id == Company.id).where(
        MaterialListing.id == listing_id,
        MaterialListing.is_active.is_(True),
        MaterialListing.created_by_brand_id.is_(None),
        Company.deleted_at.is_(None)
    )
    result = await db.execute(q)
    row = result.first()
    
    if row is None:
        raise HTTPException(status_code=404, detail="Listing not found or no longer active")
        
    out = MaterialListingOut.model_validate(row.MaterialListing)
    out.recycler_name = row.recycler_name
    out.recycler_city = row.recycler_city
    out.recycler_state = row.recycler_state
    
    return out


# ─── Purchase ─────────────────────────────────────────────────────────────────

@router.post(
    "/{listing_id}/purchase",
    response_model=MaterialPurchaseOut,
    status_code=status.HTTP_201_CREATED,
)
async def purchase_listing(
    company_id: uuid.UUID,
    listing_id: uuid.UUID,
    body: MaterialPurchaseCreate,
    deps: tuple[Company, CompanyMember] = Depends(_require_brand_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Brand purchases `quantity` units from a recycler listing.

    **Payment splits by method:**
    - **WALLET**:
        - 50% of total_price is deducted from wallet immediately.
        - 50% is frozen (ring-fenced in `frozen_wallet_balance`).
        - The brand must have `wallet_balance - frozen_wallet_balance >= total_price`
          before the purchase is accepted.
        - The frozen half is settled on delivery confirmation.
    - **DIRECT**:
        - 100% of the total_price is collected via Razorpay upfront.
        - No wallet funds are deducted or frozen.
        - Automatically confirmed by webhook when payment succeeds.

    **Inventory:** `available_quantity` is decremented atomically inside a FOR UPDATE transaction.
    """
    company, member = deps

    # ── 1. Preliminary price estimate (unlocked read) ─────────────────────
    # We do a quick unlocked read to get the price for the Razorpay order
    # creation BEFORE taking any DB locks. price_per_unit is immutable for
    # an active listing. We re-validate quantity against available_quantity
    # inside the locked section below.
    listing_preview = await db.scalar(
        select(MaterialListing)
        .join(Company, MaterialListing.recycler_id == Company.id)
        .where(
            MaterialListing.id == listing_id,
            MaterialListing.is_active.is_(True),
            MaterialListing.created_by_brand_id.is_(None),
            Company.deleted_at.is_(None)
        )
    )
    if listing_preview is None:
        raise HTTPException(status_code=404, detail="Listing not found, inactive, or recycler deleted")

    total_price: Decimal = (listing_preview.price_per_unit * body.quantity).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    if total_price <= Decimal("0.00"):
        raise HTTPException(
            status_code=400,
            detail="Purchase quantity and price are too small; total price rounds to ₹0.00."
        )

    immediate_deduction: Decimal = (total_price / 2).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    ) if body.payment_method == PaymentMethod.WALLET else Decimal("0.00")
    pending_deduction: Decimal = total_price - immediate_deduction if body.payment_method == PaymentMethod.WALLET else Decimal("0.00")

    # ── 2. Razorpay Direct Payment Order Creation (before DB locks) ───────
    # Done OUTSIDE the locked transaction so the external HTTP call does NOT
    # hold any row locks, preventing lock contention on the listing row.
    razorpay_order_id = None
    if body.payment_method == PaymentMethod.DIRECT:
        try:
            rp_order = await razorpay_client.create_order(
                amount_in_rupees=float(total_price),
                currency="INR",
                receipt=str(uuid.uuid4())[:40],
                notes={"purpose": "deal_purchase"},
            )
            razorpay_order_id = rp_order["id"]
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Failed to create Razorpay order: {e}")

    # ── 3. Lock the listing to prevent concurrent over-purchases ──────────
    # NOTE (DIRECT payment only): if listing is gone or out of stock at this
    # point, the Razorpay order created above becomes orphaned. Razorpay orders
    # with no associated payment expire automatically after 15 minutes and are
    # never charged. If the brand does pay it before expiry, the webhook will
    # raise 404 (no matching purchase row) — acceptable for this rare edge case.
    # To eliminate it entirely, call razorpay_client.close_order(razorpay_order_id)
    # in the HTTPException branches below.
    listing = await db.scalar(
        select(MaterialListing)
        .join(Company, MaterialListing.recycler_id == Company.id)
        .where(
            MaterialListing.id == listing_id,
            MaterialListing.is_active.is_(True),
            MaterialListing.created_by_brand_id.is_(None),
            Company.deleted_at.is_(None)
        )
        .with_for_update(of=MaterialListing)
    )
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found, inactive, or recycler deleted")

    if body.quantity > listing.available_quantity:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Requested quantity {body.quantity} exceeds available stock "
                f"({listing.available_quantity})."
            ),
        )

    if listing.min_order_quantity is not None:
        effective_moq = min(listing.min_order_quantity, listing.available_quantity)
        if body.quantity < effective_moq:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Requested quantity {body.quantity} is less than the effective Minimum Order Quantity "
                    f"({effective_moq})."
                ),
            )

    # Re-compute total_price from the now-locked listing to guard against a
    # price change between the unlocked preview read and this lock. If the
    # price changed for a DIRECT order, the Razorpay order amount is stale —
    # abort so the brand is never charged the wrong amount.
    locked_total_price: Decimal = (listing.price_per_unit * body.quantity).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    if locked_total_price != total_price:
        raise HTTPException(
            status_code=409,
            detail=(
                "The listing price changed while your payment was being prepared. "
                "Please retry the purchase."
            ),
        )

    # ── 4. Lock and validate company wallet (WALLET payment only) ─────────
    pending_deduction = Decimal("0.00")
    immediate_deduction = Decimal("0.00")
    if body.payment_method == PaymentMethod.WALLET:
        # Recalculate deductions from the locked price (authoritative). For
        # DIRECT, locked_total_price == total_price is already guaranteed by
        # the 409 check above, so we only need to update WALLET here.
        immediate_deduction = (locked_total_price / 2).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        pending_deduction = locked_total_price - immediate_deduction

        await db.refresh(company, with_for_update=True)
        if company.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Company not found")

        available_balance: Decimal = company.wallet_balance - company.frozen_wallet_balance
        if available_balance < locked_total_price:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Insufficient wallet balance. "
                    f"Required: ₹{locked_total_price}, "
                    f"Available: ₹{available_balance} "
                    f"(wallet: ₹{company.wallet_balance}, frozen: ₹{company.frozen_wallet_balance})."
                ),
            )

        # Deduct immediately + freeze the pending half
        company.wallet_balance -= immediate_deduction
        company.frozen_wallet_balance += pending_deduction

    # ── 5. Lock and update recycler wallet (WALLET payment only) ──────────
    # For DIRECT purchases, we do not credit the recycler until the Razorpay
    # webhook confirms the payment.
    if body.payment_method == PaymentMethod.WALLET and listing.recycler_id:
        recycler_company = await db.scalar(
            select(Company).where(Company.id == listing.recycler_id).with_for_update()
        )
        if recycler_company:
            # Credit the amount to wallet and freeze it simultaneously (pending escrow)
            recycler_company.wallet_balance += locked_total_price
            recycler_company.frozen_wallet_balance += locked_total_price

    # ── 6. Reserve inventory ──────────────────────────────────────────────
    listing.available_quantity -= body.quantity

    # ── 6. Create the purchase record ─────────────────────────────────────
    purchase = MaterialPurchase(
        listing_id=listing_id,
        brand_id=company_id,
        category=listing.category,
        purchased_quantity=body.quantity,
        total_price=locked_total_price,
        purchase_type="MARKETPLACE",
        purchase_status=PurchaseStatus.AWAITING_PAYMENT if body.payment_method == PaymentMethod.DIRECT else PurchaseStatus.PENDING,
        payment_method=body.payment_method,
        razorpay_order_id=razorpay_order_id,
        arrival_status=ArrivalStatus.PENDING,
        pending_wallet_deduction=pending_deduction,
    )
    db.add(purchase)
    await db.commit()
    await db.refresh(purchase)

    # Attach the computed immediate_deduction for the response
    out = MaterialPurchaseOut.model_validate(purchase)
    out.immediate_deduction = immediate_deduction
    return out


# ─── List own purchases (Advanced Filter) ────────────────────────────────────

@router.get("/purchases", response_model=list[MaterialPurchaseOut])
async def list_purchases(
    company_id: uuid.UUID,
    # ── Status ────────────────────────────────────────────────────────────────
    purchase_status: Optional[PurchaseStatus] = Query(default=None, description="Filter by purchase status."),
    arrival_status: Optional[ArrivalStatus] = Query(default=None, description="Filter by arrival/delivery status."),
    # ── Financial ─────────────────────────────────────────────────────────────
    payment_method: Optional[PaymentMethod] = Query(default=None, description="WALLET or DIRECT."),
    min_amount: Optional[Decimal] = Query(default=None, ge=0, description="Minimum total price (₹)."),
    max_amount: Optional[Decimal] = Query(default=None, ge=0, description="Maximum total price (₹)."),
    # ── Search ────────────────────────────────────────────────────────────────
    category: Optional[str] = Query(default=None, description="Substring search on purchase category."),
    recycler_name: Optional[str] = Query(default=None, description="Substring search on recycler company name."),
    # ── Date Range ────────────────────────────────────────────────────────────
    start_date: Optional[datetime] = Query(default=None, description="Filter purchases created on or after this datetime (UTC)."),
    end_date: Optional[datetime] = Query(default=None, description="Filter purchases created on or before this datetime (UTC)."),
    # ── Sorting & Pagination ──────────────────────────────────────────────────
    sort_by: Literal["date_desc", "date_asc", "amount_desc", "amount_asc"] = Query(default="date_desc"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    deps: tuple[Company, CompanyMember] = Depends(_require_brand),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the brand's purchase orders with advanced filtering.
    Covers both the Delivery Tracking and Purchased Invoices views.
    All filters are optional and fully combinable.
    """
    # Base query — join MaterialListing and Company to enable recycler name search
    query = (
        select(MaterialPurchase, Company.name.label("recycler_name"))
        .join(MaterialListing, MaterialPurchase.listing_id == MaterialListing.id, isouter=True)
        .join(Company, MaterialListing.recycler_id == Company.id, isouter=True)
        .where(MaterialPurchase.brand_id == company_id)
    )

    # ── Apply filters ──────────────────────────────────────────────────────────
    if purchase_status is not None:
        query = query.where(MaterialPurchase.purchase_status == purchase_status)
    if arrival_status is not None:
        query = query.where(MaterialPurchase.arrival_status == arrival_status)
    if payment_method is not None:
        query = query.where(MaterialPurchase.payment_method == payment_method)
    if min_amount is not None:
        query = query.where(MaterialPurchase.total_price >= min_amount)
    if max_amount is not None:
        query = query.where(MaterialPurchase.total_price <= max_amount)
    if category is not None:
        query = query.where(MaterialPurchase.category.ilike(f"%{category}%"))
    if recycler_name is not None:
        query = query.where(Company.name.ilike(f"%{recycler_name}%"))
    if start_date is not None:
        query = query.where(MaterialPurchase.created_at >= start_date)
    if end_date is not None:
        query = query.where(MaterialPurchase.created_at <= end_date)

    # ── Apply sorting ──────────────────────────────────────────────────────────
    if sort_by == "date_asc":
        query = query.order_by(MaterialPurchase.created_at.asc())
    elif sort_by == "amount_desc":
        query = query.order_by(MaterialPurchase.total_price.desc())
    elif sort_by == "amount_asc":
        query = query.order_by(MaterialPurchase.total_price.asc())
    else:  # date_desc (default)
        query = query.order_by(MaterialPurchase.created_at.desc())

    query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    rows = result.all()

    # immediate_deduction is not stored — reconstruct from total_price and pending.
    out = []
    for row in rows:
        p = row.MaterialPurchase
        item = MaterialPurchaseOut.model_validate(p)
        if p.payment_method == PaymentMethod.DIRECT:
            item.immediate_deduction = Decimal("0.00")
        else:
            item.immediate_deduction = p.total_price - p.pending_wallet_deduction
        item.recycler_name = row.recycler_name
        out.append(item)
    return out


@router.get("/purchased-from-recyclers", response_model=list[RecyclerProfileOut])
async def list_purchased_from_recyclers(
    company_id: uuid.UUID,
    name: Optional[str] = Query(default=None, description="Substring (case-insensitive) search on recycler company name."),
    state: Optional[str] = Query(default=None, description="Substring search on recycler state."),
    city: Optional[str] = Query(default=None, description="Substring search on recycler city."),
    material: Optional[MaterialType] = Query(default=None, description="Exact match on recycler material type (PLASTIC/METAL/BOTH)."),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    deps: tuple[Company, CompanyMember] = Depends(_require_brand),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the distinct set of Recycler companies from whom this brand has
    made at least one purchase, with optional filtering by name, location,
    and material type.
    """
    # Base query: distinct Recycler companies this brand has bought from
    query = (
        select(Company)
        .join(MaterialListing, MaterialListing.recycler_id == Company.id)
        .join(MaterialPurchase, MaterialPurchase.listing_id == MaterialListing.id)
        .where(
            MaterialPurchase.brand_id == company_id,
            MaterialPurchase.purchase_status != PurchaseStatus.CANCELLED,
            Company.deleted_at.is_(None),
        )
        .distinct()
    )

    # ── Apply filters ──────────────────────────────────────────────────────────
    if name is not None:
        query = query.where(Company.name.ilike(f"%{name}%"))
    if state is not None:
        query = query.where(Company.state.ilike(f"%{state}%"))
    if city is not None:
        query = query.where(Company.city.ilike(f"%{city}%"))
    if material is not None:
        if material in (MaterialType.PLASTIC, MaterialType.METAL):
            query = query.where(Company.material.in_([material, MaterialType.BOTH]))
        else:
            query = query.where(Company.material == material)

    query = query.order_by(Company.name.asc()).limit(limit).offset(offset)

    result = await db.execute(query)
    recyclers = result.scalars().all()
    return [RecyclerProfileOut.model_validate(r) for r in recyclers]


# ─── Download Invoice ─────────────────────────────────────────────────────────

@router.get("/purchases/{purchase_id}/invoice-download")
async def download_invoice(
    company_id: uuid.UUID,
    purchase_id: uuid.UUID,
    deps: tuple[Company, CompanyMember] = Depends(_require_brand),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns a short-lived presigned download URL for the invoice attached
    to the MaterialListing of this purchase. Cross-tenant authorized because
    the brand made the purchase.
    """
    # 1. Verify this purchase belongs to the brand
    purchase = await db.scalar(
        select(MaterialPurchase)
        .where(
            MaterialPurchase.id == purchase_id,
            MaterialPurchase.brand_id == company_id,
        )
    )
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")
        
    if purchase.purchase_status == PurchaseStatus.CANCELLED:
        raise HTTPException(status_code=403, detail="Cannot download invoice for a cancelled purchase")

    # 2. Get the listing and its invoice document ID
    listing = await db.get(MaterialListing, purchase.listing_id)
    if not listing or not listing.invoice_document_id:
        raise HTTPException(status_code=404, detail="No invoice available for this deal")

    # 3. Get the document
    document = await db.get(Document, listing.invoice_document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Invoice document record not found")

    # 4. Generate presigned URL
    download_url = generate_presigned_download_url(document.storage_key)
    return {"download_url": download_url}


# ─── Confirm delivery ─────────────────────────────────────────────────────────

@router.post("/purchases/{purchase_id}/confirm-delivery", response_model=MaterialPurchaseOut)
async def confirm_delivery(
    company_id: uuid.UUID,
    purchase_id: uuid.UUID,
    deps: tuple[Company, CompanyMember] = Depends(_require_brand_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Brand confirms that the purchased goods have arrived.
    Only valid for WALLET purchases in PENDING status.

    Settles the frozen 50%: deducts it from wallet_balance and
    releases it from frozen_wallet_balance.
    DIRECT purchases are confirmed automatically via Razorpay webhook.
    """
    company, _ = deps

    # ── 1. Lock the purchase ─────────────────────────────────────────────
    purchase = await db.scalar(
        select(MaterialPurchase).where(
            MaterialPurchase.id == purchase_id,
            MaterialPurchase.brand_id == company_id,
        ).with_for_update()
    )
    if purchase is None:
        raise HTTPException(status_code=404, detail="Purchase not found")

    # ── 1. Validate status based on payment method ───────────────────────
    if purchase.payment_method == PaymentMethod.DIRECT:
        if purchase.purchase_status != PurchaseStatus.CONFIRMED:
            raise HTTPException(
                status_code=400,
                detail="Cannot confirm delivery: payment is not confirmed yet.",
            )
        if purchase.arrival_status == ArrivalStatus.DELIVERED:
            raise HTTPException(
                status_code=400,
                detail="Delivery is already confirmed.",
            )
    else:
        if purchase.purchase_status != PurchaseStatus.PENDING:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot confirm delivery: purchase is already {purchase.purchase_status.value}.",
            )

    pending: Decimal = purchase.pending_wallet_deduction
    immediate_deduction: Decimal = purchase.total_price - pending

    # ── 2. Lock the company wallet (Brand) ───────────────────────────────
    # ALWAYS lock the Brand first to maintain a consistent lock hierarchy 
    # (Brand -> Recycler) and prevent deadlocks with create_purchase.
    await db.refresh(company, with_for_update=True)
    if company.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Company not found")

    if purchase.payment_method == PaymentMethod.WALLET:
        # Safety guard: wallet_balance should always cover the pending amount
        # because it was frozen at purchase time — but an admin could have
        # manually corrected the balance downward.
        if company.wallet_balance < pending:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Wallet balance (₹{company.wallet_balance}) is insufficient to "
                    f"settle the pending amount (₹{pending}). Please recharge the wallet."
                ),
            )

        company.wallet_balance -= pending
        company.frozen_wallet_balance -= pending

    # ── 2.5 Lock and update the recycler wallet (BOTH payment methods) ───
    listing = await db.get(MaterialListing, purchase.listing_id)
    if listing is not None and listing.recycler_id:
        recycler_company = await db.scalar(
            select(Company).where(Company.id == listing.recycler_id).with_for_update()
        )
        if recycler_company:
            # Unfreeze the funds, making them available in the wallet balance
            recycler_company.frozen_wallet_balance -= purchase.total_price

    # ── 3. Update purchase status ────────────────────────────────────────
    purchase.purchase_status = PurchaseStatus.CONFIRMED
    purchase.arrival_status = ArrivalStatus.DELIVERED
    purchase.pending_wallet_deduction = Decimal("0.00")

    # ── 4. Award EPR credits (1 Metric Ton purchased = 1 EPR credit) ─────
    # The Brand company row is already locked in step 2.
    epr_earned = purchase.purchased_quantity
    company.epr_credits_purchased += epr_earned
    company.epr_credits_available += epr_earned

    await db.commit()
    await db.refresh(purchase)

    out = MaterialPurchaseOut.model_validate(purchase)
    out.immediate_deduction = immediate_deduction
    return out


# ─── Cancel purchase ──────────────────────────────────────────────────────────

@router.post("/purchases/{purchase_id}/cancel", response_model=MaterialPurchaseOut)
async def cancel_purchase(
    company_id: uuid.UUID,
    purchase_id: uuid.UUID,
    deps: tuple[Company, CompanyMember] = Depends(_require_brand_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Cancels a PENDING or AWAITING_PAYMENT purchase.

    - For PENDING (wallet): Refunds the immediate 50% back to wallet_balance,
      releases the frozen 50% from frozen_wallet_balance.
    - For AWAITING_PAYMENT (direct): No wallet changes needed (nothing was deducted).
    - Restores listing.available_quantity in both cases.

    Not allowed once the purchase is CONFIRMED or already CANCELLED.
    """
    company, _ = deps

    # ── 1. Lock the purchase ─────────────────────────────────────────────
    purchase = await db.scalar(
        select(MaterialPurchase).where(
            MaterialPurchase.id == purchase_id,
            MaterialPurchase.brand_id == company_id,
        ).with_for_update()
    )
    if purchase is None:
        raise HTTPException(status_code=404, detail="Purchase not found")

    if purchase.purchase_status not in (PurchaseStatus.PENDING, PurchaseStatus.AWAITING_PAYMENT):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel: purchase is already {purchase.purchase_status.value}.",
        )

    pending: Decimal = purchase.pending_wallet_deduction
    immediate_deduction: Decimal = purchase.total_price - pending

    # ── 2. Lock the listing to restore inventory ─────────────────────────
    listing = await db.scalar(
        select(MaterialListing).where(
            MaterialListing.id == purchase.listing_id,
        ).with_for_update()
    )
    # Listing may have been deleted — still allow cancel but skip qty restore
    if listing is not None:
        listing.available_quantity += purchase.purchased_quantity

    # ── 3. Lock and update the company wallet (wallet purchases only) ─────
    if purchase.purchase_status == PurchaseStatus.PENDING:
        await db.refresh(company, with_for_update=True)
        if company.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Company not found")

        company.wallet_balance += immediate_deduction           # refund first half
        company.frozen_wallet_balance -= pending                # unfreeze second half

    # ── 3.5. Lock and update recycler wallet (WALLET purchases only) ───────
    if purchase.purchase_status == PurchaseStatus.PENDING and listing is not None and listing.recycler_id:
        recycler_company = await db.scalar(
            select(Company).where(Company.id == listing.recycler_id).with_for_update()
        )
        if recycler_company:
            # Revert the pending escrow
            recycler_company.wallet_balance -= purchase.total_price
            recycler_company.frozen_wallet_balance -= purchase.total_price

    # ── 4. Mark cancelled ────────────────────────────────────────────────
    purchase.purchase_status = PurchaseStatus.CANCELLED
    purchase.pending_wallet_deduction = Decimal("0.00")

    await db.commit()
    await db.refresh(purchase)

    out = MaterialPurchaseOut.model_validate(purchase)
    out.immediate_deduction = Decimal("0.00")  # refunded, no longer meaningful
    return out
