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
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import (
    Company,
    CompanyMember,
    CompanyType,
    MaterialListing,
    MaterialPurchase,
    PurchaseStatus,
    ArrivalStatus,
)
from app.schemas import (
    MaterialListingOut,
    MaterialPurchaseCreate,
    MaterialPurchaseOut,
    OfflineDealCreate,
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


# ─── Browse listings ──────────────────────────────────────────────────────────

@router.get("", response_model=list[MaterialListingOut])
async def browse_listings(
    company_id: uuid.UUID,
    material_type: str | None = None,
    category: str | None = None,
    deps: tuple[Company, CompanyMember] = Depends(_require_brand),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns all active recycler listings visible to Brands.
    Optional query params: `material_type`, `category` for basic filtering.
    """
    q = select(MaterialListing).where(
        MaterialListing.is_active.is_(True),
        MaterialListing.created_by_brand_id.is_(None)
    )

    if material_type is not None:
        q = q.where(MaterialListing.material_type == material_type)
    if category is not None:
        q = q.where(MaterialListing.category.ilike(f"%{category}%"))

    q = q.order_by(MaterialListing.created_at.desc())
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{listing_id}", response_model=MaterialListingOut)
async def get_listing_detail(
    company_id: uuid.UUID,
    listing_id: uuid.UUID,
    deps: tuple[Company, CompanyMember] = Depends(_require_brand),
    db: AsyncSession = Depends(get_db),
):
    """Returns a single active listing detail."""
    listing = await db.scalar(
        select(MaterialListing).where(
            MaterialListing.id == listing_id,
            MaterialListing.is_active.is_(True),
            MaterialListing.created_by_brand_id.is_(None)
        )
    )
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found or no longer active")
    return listing


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

    **Payment split:**
    - 50% of total_price is deducted from wallet immediately.
    - 50% is frozen (ring-fenced in `frozen_wallet_balance`).
    - The brand must have `wallet_balance - frozen_wallet_balance >= total_price`
      before the purchase is accepted.
    - The frozen half is settled on delivery confirmation.

    **Inventory:** `available_quantity` is decremented atomically with the
    wallet changes — both happen inside the same FOR UPDATE transaction.
    """
    company, member = deps

    # ── 1. Lock the listing to prevent concurrent over-purchases ────────
    listing = await db.scalar(
        select(MaterialListing).where(
            MaterialListing.id == listing_id,
            MaterialListing.is_active.is_(True),
            MaterialListing.created_by_brand_id.is_(None)
        )
        .with_for_update()
    )
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found or no longer active")

    if body.quantity > listing.available_quantity:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Requested quantity {body.quantity} exceeds available stock "
                f"({listing.available_quantity})."
            ),
        )

    # ── 2. Compute price split ───────────────────────────────────────────
    total_price: Decimal = (listing.price_per_unit * body.quantity).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    if total_price <= Decimal("0.00"):
        raise HTTPException(
            status_code=400,
            detail="Purchase quantity and price are too small; total price rounds to ₹0.00."
        )

    immediate_deduction: Decimal = (total_price / 2).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    pending_deduction: Decimal = total_price - immediate_deduction

    # ── 3. Lock and validate company wallet ─────────────────────────────
    # company is already in the identity map (from deps). Use refresh to lock and update it.
    await db.refresh(company, with_for_update=True)
    if company.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Company not found")

    available_balance: Decimal = company.wallet_balance - company.frozen_wallet_balance
    if available_balance < total_price:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Insufficient wallet balance. "
                f"Required: ₹{total_price}, "
                f"Available: ₹{available_balance} "
                f"(wallet: ₹{company.wallet_balance}, frozen: ₹{company.frozen_wallet_balance})."
            ),
        )

    # ── 4. Deduct immediately + freeze the pending half ──────────────────
    company.wallet_balance -= immediate_deduction
    company.frozen_wallet_balance += pending_deduction

    # ── 5. Reserve inventory ─────────────────────────────────────────────
    listing.available_quantity -= body.quantity

    # ── 6. Create the purchase record ────────────────────────────────────
    purchase = MaterialPurchase(
        listing_id=listing_id,
        brand_id=company_id,
        category=listing.category,
        purchased_quantity=body.quantity,
        total_price=total_price,
        purchase_type="MARKETPLACE",
        purchase_status=PurchaseStatus.PENDING,
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


# ─── List own purchases ───────────────────────────────────────────────────────

@router.get("/purchases", response_model=list[MaterialPurchaseOut])
async def list_purchases(
    company_id: uuid.UUID,
    deps: tuple[Company, CompanyMember] = Depends(_require_brand),
    db: AsyncSession = Depends(get_db),
):
    """Returns all purchases made by this brand, newest first."""
    result = await db.execute(
        select(MaterialPurchase)
        .where(MaterialPurchase.brand_id == company_id)
        .order_by(MaterialPurchase.created_at.desc())
    )
    purchases = result.scalars().all()

    # immediate_deduction is not stored — reconstruct it from total_price and pending
    out = []
    for p in purchases:
        item = MaterialPurchaseOut.model_validate(p)
        item.immediate_deduction = p.total_price - p.pending_wallet_deduction
        out.append(item)
    return out


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
    Settles the frozen 50%: deducts it from wallet_balance and
    releases it from frozen_wallet_balance.

    Only allowed when purchase_status == PENDING.
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

    if purchase.purchase_status != PurchaseStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot confirm delivery: purchase is already {purchase.purchase_status.value}.",
        )

    pending: Decimal = purchase.pending_wallet_deduction
    immediate_deduction: Decimal = purchase.total_price - pending

    # ── 2. Lock and update the company wallet ────────────────────────────
    await db.refresh(company, with_for_update=True)
    if company.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Company not found")

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

    # ── 3. Update purchase status ────────────────────────────────────────
    purchase.purchase_status = PurchaseStatus.CONFIRMED
    purchase.arrival_status = ArrivalStatus.DELIVERED
    purchase.pending_wallet_deduction = Decimal("0.00")

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
    Cancels a PENDING purchase.

    - Refunds the immediate 50% back to wallet_balance.
    - Releases the frozen 50% from frozen_wallet_balance.
    - Restores listing.available_quantity.

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

    if purchase.purchase_status != PurchaseStatus.PENDING:
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

    # ── 3. Lock and update the company wallet ────────────────────────────
    await db.refresh(company, with_for_update=True)
    if company.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Company not found")

    company.wallet_balance += immediate_deduction           # refund first half
    company.frozen_wallet_balance -= pending                # unfreeze second half

    # ── 4. Mark cancelled ────────────────────────────────────────────────
    purchase.purchase_status = PurchaseStatus.CANCELLED
    purchase.pending_wallet_deduction = Decimal("0.00")

    await db.commit()
    await db.refresh(purchase)

    out = MaterialPurchaseOut.model_validate(purchase)
    out.immediate_deduction = Decimal("0.00")  # refunded, no longer meaningful
    return out
