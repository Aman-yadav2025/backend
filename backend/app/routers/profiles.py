import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Company, CompanyMember, MemberRole, MemberStatus, Profile
from app.security import get_current_profile
from app.services.clerk_client import delete_user, ClerkAPIError

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.delete("/me", status_code=status.HTTP_200_OK)
async def delete_my_profile(
    profile: Profile = Depends(get_current_profile),
    db: AsyncSession = Depends(get_db),
):
    """
    Deletes the current user's profile.
    Must not be the sole OWNER of any active company.

    Flow:
      1. Unprotected read to discover which companies to lock.
      2. Acquire Company → Profile locks (global hierarchy).
      3. Locked re-read to prevent TOCTOU.
      4. Validate: user must not be the sole active owner of any company.
      5. Call Clerk to delete the user (404 is treated as success on retry).
      6. Hard-delete the Profile row. CompanyMember rows cascade automatically.
      7. Commit.

    The `user.deleted` webhook is a redundant safety net, not the primary cleanup path.
    """
    # ── Step 1: Unprotected read to find companies we need to lock ──────────
    initial_memberships_res = await db.execute(
        select(CompanyMember.company_id)
        .join(Company, Company.id == CompanyMember.company_id)
        .where(
            CompanyMember.profile_id == profile.id,
            CompanyMember.status == MemberStatus.ACTIVE,
            Company.deleted_at.is_(None),
        )
    )
    all_company_ids = initial_memberships_res.scalars().all()

    # ── Step 2: Acquire locks in consistent order (prevents deadlocks) ───────
    for company_id in sorted(all_company_ids):
        await db.execute(
            select(Company.id).where(Company.id == company_id).with_for_update()
        )

    # Lock Profile (Company → Profile hierarchy)
    await db.execute(
        select(Profile.id).where(Profile.id == profile.id).with_for_update()
    )

    # ── Step 3: Locked re-read to prevent TOCTOU on membership rows ─────────
    locked_memberships_res = await db.execute(
        select(CompanyMember)
        .join(Company, Company.id == CompanyMember.company_id)
        .where(
            CompanyMember.profile_id == profile.id,
            CompanyMember.status == MemberStatus.ACTIVE,
            Company.deleted_at.is_(None),
        )
    )
    memberships = locked_memberships_res.scalars().all()

    current_company_ids = {m.company_id for m in memberships}
    if not current_company_ids.issubset(set(all_company_ids)):
        # A new membership was added concurrently after our initial read.
        # We cannot lock the new company without violating the lock hierarchy
        # (Company must be locked BEFORE Profile), so abort safely.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Your memberships changed while processing. Please try again.",
        )

    # ── Step 4: Sole-owner guard ─────────────────────────────────────────────
    owned_company_ids = [
        m.company_id for m in memberships if m.member_role == MemberRole.OWNER
    ]
    for company_id in owned_company_ids:
        other_owners_res = await db.execute(
            select(CompanyMember.id).where(
                CompanyMember.company_id == company_id,
                CompanyMember.member_role == MemberRole.OWNER,
                CompanyMember.status == MemberStatus.ACTIVE,
                CompanyMember.profile_id != profile.id,
            ).with_for_update()
        )
        if not other_owners_res.first():
            raise HTTPException(
                status_code=400,
                detail="You are the sole admin of a company. Transfer ownership or delete the company first.",
            )

    # ── Step 5: Delete from Clerk (while DB locks are still held) ────────────
    # 404 from Clerk means the user was already deleted — treat as success (idempotent retry).
    try:
        await delete_user(profile.id)
    except ClerkAPIError as e:
        logging.exception("Clerk delete_user failed for %s", profile.id)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete account in authentication provider: {e}",
        )

    # ── Step 6: Hard-delete the Profile row ──────────────────────────────────
    # CompanyMember rows cascade-delete automatically (FK ondelete=CASCADE).
    # This is the authoritative DB cleanup — the webhook is a redundant safety net only.
    await db.execute(delete(Profile).where(Profile.id == profile.id))

    # ── Step 7: Commit ───────────────────────────────────────────────────────
    await db.commit()

    return {"message": "Account deleted successfully"}

