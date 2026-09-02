"""
Marketplace router — Material Listings
=======================================
Endpoints for Recyclers to manage their material deals.
Brands browsing/purchasing listings will be in a separate router.

Endpoint summary:
  POST   /companies/{company_id}/listings                    — Create a new listing
  GET    /companies/{company_id}/listings                    — List own company's listings
  GET    /companies/{company_id}/listings/{id}               — Get a single listing
  PATCH  /companies/{company_id}/listings/{id}               — Update a listing
  PATCH  /companies/{company_id}/listings/{id}/invoice       — Attach or replace invoice
  DELETE /companies/{company_id}/listings/{id}               — Deactivate a listing

Invoice / Risk flow:
  - Recycler uploads invoice via the existing presign → confirm document flow.
  - They pass the returned document UUID as `invoice_document_id` at listing
    creation time, or attach it later via PATCH /{id}/invoice.
  - The risk evaluator is called on create AND on invoice attachment.
  - No invoice present → validity_risk is always forced to "HIGHEST RISK".
"""

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import (
    Company,
    CompanyMember,
    CompanyType,
    Document,
    MaterialListing,
    MaterialPurchase,
    PurchaseStatus,
)
from app.schemas import (
    MaterialListingCreate,
    MaterialListingInvoiceAttach,
    MaterialListingOut,
    MaterialListingUpdate,
    MaterialPurchaseOut,
    ArrivalStatusUpdate,
)
from app.security import require_company_admin
from app.services.risk_evaluator import evaluate_listing_risk

router = APIRouter(prefix="/companies/{company_id}/listings", tags=["marketplace-listings"])


# ─── Shared dependency: verify RECYCLER company admin ────────────────────────

async def _require_recycler_admin(
    company_id: uuid.UUID,
    _admin: CompanyMember = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
) -> Company:
    """
    Verifies the caller is an OWNER-level member of the company AND that the
    company is a RECYCLER.  Uses a plain (non-locking) read here so that the
    company row is NOT locked for the duration of evaluate_listing_risk() —
    when the algorithm makes external HTTP calls, a FOR UPDATE would block all
    concurrent company updates for the full call duration.
    The listing-level FOR UPDATE in each write endpoint is sufficient for
    data integrity.
    """
    company = await db.scalar(
        select(Company).where(
            Company.id == company_id,
            Company.deleted_at.is_(None),
        )
    )
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    if company.company_type != CompanyType.RECYCLER:
        raise HTTPException(
            status_code=403,
            detail="Only RECYCLER companies can manage material listings",
        )
    return company


async def _validate_invoice_doc(
    invoice_document_id: uuid.UUID,
    company_id: uuid.UUID,
    db: AsyncSession,
) -> Document:
    """
    Confirms the invoice document exists and belongs to the recycler's company.
    Takes a FOR UPDATE lock to prevent a concurrent delete from racing between
    this check and the subsequent listing insert/update.
    """
    result = await db.execute(
        select(Document).where(
            Document.id == invoice_document_id,
            Document.company_id == company_id,
        ).with_for_update()
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Invoice document not found or does not belong to this company. "
                "Upload the document first using the /documents endpoints."
            ),
        )
    return doc


# ─── Create ──────────────────────────────────────────────────────────────────

@router.post("", response_model=MaterialListingOut, status_code=status.HTTP_201_CREATED)
async def create_listing(
    company_id: uuid.UUID,
    body: MaterialListingCreate,
    company: Company = Depends(_require_recycler_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Recycler posts a new material deal.

    **Invoice:**
    Pass `invoice_document_id` pointing to a document you have already
    uploaded via `POST /companies/{id}/documents`.  Without it, the deal
    is automatically flagged as **HIGHEST RISK**.

    **Risk evaluation:**
    `evaluate_listing_risk()` runs immediately after the listing is flushed.
    When the full algorithm is implemented in `services/risk_evaluator.py`,
    this endpoint requires no further changes.
    """
    # Validate invoice document ownership before creating the listing
    if body.invoice_document_id is not None:
        await _validate_invoice_doc(body.invoice_document_id, company_id, db)

    if body.min_order_quantity is not None and body.min_order_quantity > body.total_quantity:
        raise HTTPException(
            status_code=400,
            detail=f"Minimum order quantity ({body.min_order_quantity}) cannot exceed total quantity ({body.total_quantity})."
        )

    listing = MaterialListing(
        recycler_id=company_id,
        material_type=body.material_type,
        category=body.category,
        grade=body.grade,
        price_per_unit=body.price_per_unit,
        total_quantity=body.total_quantity,
        available_quantity=body.total_quantity,  # nothing sold yet
        invoice_document_id=body.invoice_document_id,
        validity_risk=body.validity_risk,
        description=body.description,
        batch_inspection_report=body.batch_inspection_report,
        min_order_quantity=body.min_order_quantity,
        carbon_reduction_per_kg=body.carbon_reduction_per_kg,
        water_conservation_per_kg=body.water_conservation_per_kg,
        accreditations=body.accreditations,
        technical_parameters=body.technical_parameters,
        is_active=True,
    )
    db.add(listing)
    await db.flush()  # populate listing.id before calling the evaluator

    # Risk evaluation always runs — no-invoice rule is enforced here.
    listing.validity_risk = await evaluate_listing_risk(listing)

    await db.commit()
    await db.refresh(listing)
    
    out = MaterialListingOut.model_validate(listing)
    out.recycler_name = company.name
    out.recycler_city = company.city
    out.recycler_state = company.state
    return out


# ─── List own listings ────────────────────────────────────────────────────────

@router.get("", response_model=list[MaterialListingOut])
async def list_listings(
    company_id: uuid.UUID,
    include_inactive: bool = False,
    limit: int | None = None,
    offset: int = 0,
    _admin: CompanyMember = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns all listings for the recycler's company.
    Pass `?include_inactive=true` to also see deactivated listings.
    """
    company = await db.scalar(
        select(Company).where(Company.id == company_id, Company.deleted_at.is_(None))
    )
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    if company.company_type != CompanyType.RECYCLER:
        raise HTTPException(status_code=403, detail="Only RECYCLER companies can access this resource")

    q = select(
        MaterialListing,
        Company.name.label("recycler_name"),
        Company.city.label("recycler_city"),
        Company.state.label("recycler_state")
    ).outerjoin(Company, MaterialListing.recycler_id == Company.id)
    
    q = q.where(MaterialListing.recycler_id == company_id)
    if not include_inactive:
        q = q.where(MaterialListing.is_active.is_(True))
    q = q.order_by(MaterialListing.created_at.desc())
    
    if limit is not None:
        q = q.limit(limit)
    if offset > 0:
        q = q.offset(offset)

    result = await db.execute(q)
    rows = result.all()
    
    out_list = []
    for row in rows:
        listing = row.MaterialListing
        out = MaterialListingOut.model_validate(listing)
        out.recycler_name = row.recycler_name
        out.recycler_city = row.recycler_city
        out.recycler_state = row.recycler_state
        out_list.append(out)
        
    return out_list


# ─── Get single listing ───────────────────────────────────────────────────────

@router.get("/{listing_id}", response_model=MaterialListingOut)
async def get_listing(
    company_id: uuid.UUID,
    listing_id: uuid.UUID,
    _admin: CompanyMember = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    # Guard: Brand admins calling with their own company_id must get 403,
    # not a silent 404, to avoid leaking information about listing UUIDs.
    company = await db.scalar(
        select(Company).where(Company.id == company_id, Company.deleted_at.is_(None))
    )
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    if company.company_type != CompanyType.RECYCLER:
        raise HTTPException(status_code=403, detail="Only RECYCLER companies can access this resource")

    q = select(
        MaterialListing,
        Company.name.label("recycler_name"),
        Company.city.label("recycler_city"),
        Company.state.label("recycler_state")
    ).outerjoin(Company, MaterialListing.recycler_id == Company.id).where(
        MaterialListing.id == listing_id,
        MaterialListing.recycler_id == company_id,
    )
    result = await db.execute(q)
    row = result.first()
    
    if row is None:
        raise HTTPException(status_code=404, detail="Listing not found")
        
    out = MaterialListingOut.model_validate(row.MaterialListing)
    out.recycler_name = row.recycler_name
    out.recycler_city = row.recycler_city
    out.recycler_state = row.recycler_state
    
    return out


# ─── Attach / replace invoice ─────────────────────────────────────────────────

@router.patch("/{listing_id}/invoice", response_model=MaterialListingOut)
async def attach_invoice(
    company_id: uuid.UUID,
    listing_id: uuid.UUID,
    body: MaterialListingInvoiceAttach,
    company: Company = Depends(_require_recycler_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Attach or replace the invoice document for a listing.

    After a successful attach, the risk evaluator runs immediately —
    so validity_risk will be updated from **HIGHEST RISK** to the algorithm's
    output (or **MEDIUM RISK** by default until the algorithm is live).

    **Flow:**
    1. Recycler uploads the invoice PDF via `POST /companies/{id}/documents`.
    2. Recycler calls this endpoint with the returned `document_id`.
    3. The listing's `validity_risk` is re-evaluated and updated.

    **Locking order:** Company → Listing → Document  (deadlock-safe)
    """
    # Lock the listing first (Company is already locked by _require_recycler_admin).
    # We validate the document AFTER locking the listing so the entire
    # check-then-act is inside a single serialized transaction.
    result = await db.execute(
        select(MaterialListing).where(
            MaterialListing.id == listing_id,
            MaterialListing.recycler_id == company_id,
        ).with_for_update()
    )
    listing = result.scalar_one_or_none()
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")

    # Validate + lock the document AFTER the listing lock is held.
    await _validate_invoice_doc(body.invoice_document_id, company_id, db)

    listing.invoice_document_id = body.invoice_document_id

    # Re-evaluate risk now that the invoice is attached
    listing.validity_risk = await evaluate_listing_risk(listing)

    await db.commit()
    await db.refresh(listing)
    
    out = MaterialListingOut.model_validate(listing)
    out.recycler_name = company.name
    out.recycler_city = company.city
    out.recycler_state = company.state
    return out


# ─── Update listing ───────────────────────────────────────────────────────────

@router.patch("/{listing_id}", response_model=MaterialListingOut)
async def update_listing(
    company_id: uuid.UUID,
    listing_id: uuid.UUID,
    body: MaterialListingUpdate,
    company: Company = Depends(_require_recycler_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Partial update.  Only supplied fields are changed.

    Business rules enforced here:
    - `total_quantity` can only be increased, never decreased below the
      amount already sold (`total_quantity - available_quantity`).
    - Setting `is_active=False` preserves the row but hides it from Brands.
    - Note: to change the invoice, use `PATCH /{listing_id}/invoice` instead.
    """
    result = await db.execute(
        select(MaterialListing).where(
            MaterialListing.id == listing_id,
            MaterialListing.recycler_id == company_id,
        ).with_for_update()
    )
    listing = result.scalar_one_or_none()
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")

    update_data = body.model_dump(exclude_unset=True)
    
    if "category" in update_data:
        listing.category = update_data["category"]
    if "grade" in update_data:
        listing.grade = update_data["grade"]
    if "price_per_unit" in update_data:
        listing.price_per_unit = update_data["price_per_unit"]

    if "total_quantity" in update_data:
        sold_quantity: Decimal = listing.total_quantity - listing.available_quantity
        if update_data["total_quantity"] < sold_quantity:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot set total_quantity to {update_data['total_quantity']} — "
                    f"{sold_quantity} units are already sold."
                ),
            )
        listing.available_quantity = update_data["total_quantity"] - sold_quantity
        listing.total_quantity = update_data["total_quantity"]

    if "validity_risk" in update_data:
        if listing.invoice_document_id is None:
            raise HTTPException(
                status_code=400,
                detail="Cannot override validity_risk without an invoice. Attach an invoice first.",
            )
        listing.validity_risk = update_data["validity_risk"]

    if "description" in update_data:
        listing.description = update_data["description"]
    if "batch_inspection_report" in update_data:
        listing.batch_inspection_report = update_data["batch_inspection_report"]
    if "min_order_quantity" in update_data:
        listing.min_order_quantity = update_data["min_order_quantity"]
    if "carbon_reduction_per_kg" in update_data:
        listing.carbon_reduction_per_kg = update_data["carbon_reduction_per_kg"]
    if "water_conservation_per_kg" in update_data:
        listing.water_conservation_per_kg = update_data["water_conservation_per_kg"]
    if "accreditations" in update_data:
        listing.accreditations = update_data["accreditations"]
    if "technical_parameters" in update_data:
        listing.technical_parameters = update_data["technical_parameters"]
    if "is_active" in update_data:
        listing.is_active = update_data["is_active"]

    if listing.min_order_quantity is not None and listing.min_order_quantity > listing.total_quantity:
        raise HTTPException(
            status_code=400,
            detail=f"Minimum order quantity ({listing.min_order_quantity}) cannot exceed total quantity ({listing.total_quantity})."
        )

    await db.commit()
    await db.refresh(listing)
    
    out = MaterialListingOut.model_validate(listing)
    out.recycler_name = company.name
    out.recycler_city = company.city
    out.recycler_state = company.state
    return out


# ─── Deactivate (soft delete) listing ────────────────────────────────────────

@router.delete("/{listing_id}", status_code=status.HTTP_200_OK)
async def deactivate_listing(
    company_id: uuid.UUID,
    listing_id: uuid.UUID,
    company: Company = Depends(_require_recycler_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Deactivates the listing (sets is_active=False).  Does NOT hard-delete it
    so that existing purchases still reference a valid listing row.
    """
    result = await db.execute(
        select(MaterialListing).where(
            MaterialListing.id == listing_id,
            MaterialListing.recycler_id == company_id,
        ).with_for_update()
    )
    listing = result.scalar_one_or_none()
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")

    if not listing.is_active:
        # Release the lock explicitly before returning — nothing to commit.
        await db.rollback()
        return {"message": "Listing is already inactive"}

    listing.is_active = False
    await db.commit()
    return {"message": "Listing deactivated successfully"}


# ─── Update purchase arrival status ──────────────────────────────────────────

@router.patch("/{listing_id}/purchases/{purchase_id}/arrival-status", response_model=MaterialPurchaseOut)
async def update_purchase_arrival_status(
    company_id: uuid.UUID,
    listing_id: uuid.UUID,
    purchase_id: uuid.UUID,
    body: ArrivalStatusUpdate,
    company: Company = Depends(_require_recycler_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Allows a Recycler to update the arrival status of a material deal (purchase).
    """
    # Find the listing to ensure the purchase belongs to this recycler
    result = await db.execute(
        select(MaterialListing).where(
            MaterialListing.id == listing_id,
            MaterialListing.recycler_id == company_id,
        )
    )
    listing = result.scalar_one_or_none()
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")

    # Find the purchase and lock it for update
    purchase_result = await db.execute(
        select(MaterialPurchase).where(
            MaterialPurchase.id == purchase_id,
            MaterialPurchase.listing_id == listing_id,
        ).with_for_update()
    )
    purchase = purchase_result.scalar_one_or_none()
    if purchase is None:
        raise HTTPException(status_code=404, detail="Purchase not found")

    if purchase.purchase_status in (PurchaseStatus.AWAITING_PAYMENT, PurchaseStatus.CANCELLED):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot update arrival status: purchase is {purchase.purchase_status.value}.",
        )

    purchase.arrival_status = body.arrival_status
    await db.commit()
    await db.refresh(purchase)
    
    out = MaterialPurchaseOut.model_validate(purchase)
    out.immediate_deduction = Decimal("0.00")
    return out
