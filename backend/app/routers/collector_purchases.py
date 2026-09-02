import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
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
