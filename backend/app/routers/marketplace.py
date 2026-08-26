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
)
from app.schemas import (
    MaterialListingCreate,
    MaterialListingInvoiceAttach,
    MaterialListingOut,
    MaterialListingUpdate,
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
        is_active=True,
    )
    db.add(listing)
    await db.flush()  # populate listing.id before calling the evaluator

    # Risk evaluation always runs — no-invoice rule is enforced here.
    listing.validity_risk = await evaluate_listing_risk(listing)

    await db.commit()
    await db.refresh(listing)
    return listing


# ─── List own listings ────────────────────────────────────────────────────────

@router.get("", response_model=list[MaterialListingOut])
async def list_listings(
    company_id: uuid.UUID,
    include_inactive: bool = False,
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

    q = select(MaterialListing).where(MaterialListing.recycler_id == company_id)
    if not include_inactive:
        q = q.where(MaterialListing.is_active.is_(True))
    q = q.order_by(MaterialListing.created_at.desc())

    result = await db.execute(q)
    return result.scalars().all()


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

    listing = await db.scalar(
        select(MaterialListing).where(
            MaterialListing.id == listing_id,
            MaterialListing.recycler_id == company_id,
        )
    )
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    return listing


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
    return listing


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

    if body.category is not None:
        listing.category = body.category

    if body.grade is not None:
        listing.grade = body.grade

    if body.price_per_unit is not None:
        listing.price_per_unit = body.price_per_unit

    if body.total_quantity is not None:
        sold_quantity: Decimal = listing.total_quantity - listing.available_quantity
        if body.total_quantity < sold_quantity:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot set total_quantity to {body.total_quantity} — "
                    f"{sold_quantity} units are already sold."
                ),
            )
        listing.available_quantity = body.total_quantity - sold_quantity
        listing.total_quantity = body.total_quantity

    if body.validity_risk is not None:
        # Manual override is allowed ONLY when invoice is present —
        # without invoice the risk is always HIGHEST RISK.
        if listing.invoice_document_id is None:
            raise HTTPException(
                status_code=400,
                detail="Cannot override validity_risk without an invoice. Attach an invoice first.",
            )
        listing.validity_risk = body.validity_risk

    if body.is_active is not None:
        listing.is_active = body.is_active

    await db.commit()
    await db.refresh(listing)
    return listing


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
