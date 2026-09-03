import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.models import (
    CompanyMember,
    CollectorPurchase,
    Document,
    MemberRole,
    MemberStatus,
    Profile,
)
from app.schemas import (
    CollectorPurchaseCreate,
    CollectorPurchaseUpdate,
    CollectorPurchaseOut,
)
from app.security import get_current_profile, require_active_company_membership

router = APIRouter(prefix="/companies/{company_id}/collector-purchases", tags=["collector-purchases"])


# ─── Advanced List (Search) ───────────────────────────────────────────────────

@router.get("", response_model=list[CollectorPurchaseOut])
async def list_collector_purchases(
    company_id: uuid.UUID,
    # ── Collector Search ──────────────────────────────────────────────────────
    collector_name: Optional[str] = Query(default=None, description="Substring (case-insensitive) search on collector name."),
    collector_company_name: Optional[str] = Query(default=None, description="Substring search on collector company name."),
    # ── Material ──────────────────────────────────────────────────────────────
    category: Optional[str] = Query(default=None, description="Exact enum value: PLASTIC, METAL, or BOTH."),
    material_type: Optional[str] = Query(default=None, description="Substring search on the free-text material_type field."),
    # ── Financial ─────────────────────────────────────────────────────────────
    min_amount: Optional[Decimal] = Query(default=None, ge=0, description="Minimum purchase price (₹)."),
    max_amount: Optional[Decimal] = Query(default=None, ge=0, description="Maximum purchase price (₹)."),
    # ── Date Range ────────────────────────────────────────────────────────────
    start_date: Optional[datetime] = Query(default=None, description="Filter records created on or after this datetime (UTC)."),
    end_date: Optional[datetime] = Query(default=None, description="Filter records created on or before this datetime (UTC)."),
    # ── Sorting & Pagination ──────────────────────────────────────────────────
    sort_by: Literal["date_desc", "date_asc", "amount_desc", "amount_asc"] = Query(default="date_desc"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    membership: CompanyMember = Depends(require_active_company_membership),
    profile: Profile = Depends(get_current_profile),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns collector purchases for this Recycler company with advanced filtering.
    OWNER members see all purchases; MEMBER-role users see only their own records.
    All filters are optional and fully combinable.
    """
    query = select(CollectorPurchase).where(CollectorPurchase.recycler_id == company_id)

    # Members (non-OWNERs) can only see their own purchases
    if membership.member_role != MemberRole.OWNER:
        query = query.where(CollectorPurchase.created_by_profile_id == profile.id)

    # ── Apply filters ──────────────────────────────────────────────────────────
    if collector_name is not None:
        query = query.where(CollectorPurchase.collector_name.ilike(f"%{collector_name}%"))
    if collector_company_name is not None:
        query = query.where(CollectorPurchase.collector_company_name.ilike(f"%{collector_company_name}%"))
    if category is not None:
        query = query.where(CollectorPurchase.category == category)
    if material_type is not None:
        query = query.where(CollectorPurchase.material_type.ilike(f"%{material_type}%"))
    if min_amount is not None:
        query = query.where(CollectorPurchase.price >= min_amount)
    if max_amount is not None:
        query = query.where(CollectorPurchase.price <= max_amount)
    if start_date is not None:
        query = query.where(CollectorPurchase.created_at >= start_date)
    if end_date is not None:
        query = query.where(CollectorPurchase.created_at <= end_date)

    # ── Apply sorting ──────────────────────────────────────────────────────────
    if sort_by == "date_asc":
        query = query.order_by(CollectorPurchase.created_at.asc())
    elif sort_by == "amount_desc":
        query = query.order_by(CollectorPurchase.price.desc())
    elif sort_by == "amount_asc":
        query = query.order_by(CollectorPurchase.price.asc())
    else:  # date_desc (default)
        query = query.order_by(CollectorPurchase.created_at.desc())

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{purchase_id}", response_model=CollectorPurchaseOut)
async def get_collector_purchase(
    company_id: uuid.UUID,
    purchase_id: uuid.UUID,
    membership: CompanyMember = Depends(require_active_company_membership),
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch a single collector purchase record by its ID.
    """
    purchase = (await db.execute(
        select(CollectorPurchase)
        .where(
            CollectorPurchase.id == purchase_id,
            CollectorPurchase.recycler_id == company_id,
        )
    )).scalar_one_or_none()

    if not purchase:
        raise HTTPException(status_code=404, detail="Collector purchase not found")

    return purchase




class AttachDocumentRequest(BaseModel):
    document_id: uuid.UUID


def _can_mutate(membership: CompanyMember, purchase: CollectorPurchase, profile: Profile) -> bool:
    """
    True if the caller may update or delete this purchase:
      - OWNER role: always allowed.
      - MEMBER role: only the original creator.
      - Legacy rows (created_by_profile_id is NULL): OWNER-only.
    """
    if membership.member_role == MemberRole.OWNER:
        return True
    if purchase.created_by_profile_id is None:
        return False  # Legacy row — treat as owner-only
    return purchase.created_by_profile_id == profile.id


async def _recheck_membership(db: AsyncSession, membership: CompanyMember) -> None:
    """Re-validates that membership has not been revoked since the JWT was issued."""
    if membership.id is None:
        return  # Synthetic PLATFORM_ADMIN membership — always valid
    fresh = (await db.execute(
        select(CompanyMember).where(
            CompanyMember.id == membership.id,
            CompanyMember.status == MemberStatus.ACTIVE,
        ).with_for_update()
    )).scalar_one_or_none()
    if fresh is None:
        raise HTTPException(status_code=403, detail="Membership revoked during request")


@router.post("", response_model=CollectorPurchaseOut, status_code=201)
async def create_collector_purchase(
    company_id: uuid.UUID,
    payload: CollectorPurchaseCreate,
    membership: CompanyMember = Depends(require_active_company_membership),
    profile: Profile = Depends(get_current_profile),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new collector purchase for the company.
    The calling profile is recorded as the creator.
    """
    await _recheck_membership(db, membership)

    if payload.document_id:
        doc = (await db.execute(
            select(Document).where(
                Document.id == payload.document_id,
                Document.company_id == company_id,
            )
        )).scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=403, detail="Document not found or unauthorized")

    new_purchase = CollectorPurchase(
        recycler_id=company_id,
        created_by_profile_id=profile.id,
        collector_name=payload.collector_name,
        collector_company_name=payload.collector_company_name,
        mobile_number=payload.mobile_number,
        gst_number=payload.gst_number,
        address=payload.address,
        category=payload.category,
        material_type=payload.material_type,
        quantity=payload.quantity,
        price=payload.price,
        document_id=payload.document_id,
    )

    db.add(new_purchase)
    await db.commit()
    await db.refresh(new_purchase)

    return new_purchase


@router.patch("/{purchase_id}", response_model=CollectorPurchaseOut)
async def update_collector_purchase(
    company_id: uuid.UUID,
    purchase_id: uuid.UUID,
    payload: CollectorPurchaseUpdate,
    membership: CompanyMember = Depends(require_active_company_membership),
    profile: Profile = Depends(get_current_profile),
    db: AsyncSession = Depends(get_db),
):
    """
    Update an existing collector purchase.
    Only the original creator or an OWNER may update.
    """
    purchase = (await db.execute(
        select(CollectorPurchase)
        .where(
            CollectorPurchase.id == purchase_id,
            CollectorPurchase.recycler_id == company_id,
        )
        .with_for_update()
    )).scalar_one_or_none()

    if not purchase:
        raise HTTPException(status_code=404, detail="Collector purchase not found")

    await _recheck_membership(db, membership)

    if not _can_mutate(membership, purchase, profile):
        raise HTTPException(
            status_code=403,
            detail="Not authorized — only the creator or an OWNER can update this purchase",
        )

    update_data = payload.model_dump(exclude_unset=True)

    if "document_id" in update_data and update_data["document_id"] is not None:
        doc = (await db.execute(
            select(Document).where(
                Document.id == update_data["document_id"],
                Document.company_id == company_id,
            )
        )).scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=403, detail="Document not found or unauthorized")

    for key, value in update_data.items():
        setattr(purchase, key, value)

    await db.commit()
    await db.refresh(purchase)

    return purchase


@router.delete("/{purchase_id}", status_code=204)
async def delete_collector_purchase(
    company_id: uuid.UUID,
    purchase_id: uuid.UUID,
    membership: CompanyMember = Depends(require_active_company_membership),
    profile: Profile = Depends(get_current_profile),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a collector purchase.
    Only the original creator or an OWNER may delete.
    """
    purchase = (await db.execute(
        select(CollectorPurchase)
        .where(
            CollectorPurchase.id == purchase_id,
            CollectorPurchase.recycler_id == company_id,
        )
        .with_for_update()
    )).scalar_one_or_none()

    if not purchase:
        raise HTTPException(status_code=404, detail="Collector purchase not found")

    await _recheck_membership(db, membership)

    if not _can_mutate(membership, purchase, profile):
        raise HTTPException(
            status_code=403,
            detail="Not authorized — only the creator or an OWNER can delete this purchase",
        )

    await db.delete(purchase)
    await db.commit()


@router.patch("/{purchase_id}/document", response_model=CollectorPurchaseOut)
async def attach_document_to_collector_purchase(
    company_id: uuid.UUID,
    purchase_id: uuid.UUID,
    body: AttachDocumentRequest,
    membership: CompanyMember = Depends(require_active_company_membership),
    profile: Profile = Depends(get_current_profile),
    db: AsyncSession = Depends(get_db),
):
    """
    Attaches an uploaded document to a specific collector purchase.
    Only the original creator or an OWNER may attach documents.
    """
    purchase = (await db.execute(
        select(CollectorPurchase).where(
            CollectorPurchase.id == purchase_id,
            CollectorPurchase.recycler_id == company_id,
        ).with_for_update()
    )).scalar_one_or_none()

    if not purchase:
        raise HTTPException(status_code=404, detail="Collector purchase not found")

    await _recheck_membership(db, membership)

    if not _can_mutate(membership, purchase, profile):
        raise HTTPException(
            status_code=403,
            detail="Not authorized — only the creator or an OWNER can modify this purchase",
        )

    doc = (await db.execute(
        select(Document).where(
            Document.id == body.document_id,
            Document.company_id == company_id,
        )
    )).scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found or access denied")

    purchase.document_id = doc.id
    await db.commit()
    await db.refresh(purchase)

    return purchase
