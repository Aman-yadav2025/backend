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
    PaymentMethod,
    Document,
)
from app.services import razorpay_client
from app.services.r2_storage import generate_presigned_download_url
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
        select(MaterialListing).where(
            MaterialListing.id == listing_id,
            MaterialListing.is_active.is_(True),
            MaterialListing.created_by_brand_id.is_(None),
        )
    )
    if listing_preview is None:
        raise HTTPException(status_code=404, detail="Listing not found or no longer active")

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
        select(MaterialListing).where(
            MaterialListing.id == listing_id,
            MaterialListing.is_active.is_(True),
            MaterialListing.created_by_brand_id.is_(None),
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

    # ── 5. Reserve inventory ──────────────────────────────────────────────
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

    # immediate_deduction is not stored — reconstruct it from total_price and pending.
    # For DIRECT purchases nothing was deducted from the wallet, so it is always 0.
    out = []
    for p in purchases:
        item = MaterialPurchaseOut.model_validate(p)
        if p.payment_method == PaymentMethod.DIRECT:
            item.immediate_deduction = Decimal("0.00")
        else:
            item.immediate_deduction = p.total_price - p.pending_wallet_deduction
        out.append(item)
    return out


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

    # ── 2. Lock and update the company wallet (WALLET only) ──────────────
    if purchase.payment_method == PaymentMethod.WALLET:
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

    # ── 4. Mark cancelled ────────────────────────────────────────────────
    purchase.purchase_status = PurchaseStatus.CANCELLED
    purchase.pending_wallet_deduction = Decimal("0.00")

    await db.commit()
    await db.refresh(purchase)

    out = MaterialPurchaseOut.model_validate(purchase)
    out.immediate_deduction = Decimal("0.00")  # refunded, no longer meaningful
    return out
