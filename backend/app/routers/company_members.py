import uuid

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Company, CompanyMember, MemberRole, MemberStatus, Profile, SystemRole
from app.schemas import CompanyMemberOut, CompanyMemberStatusUpdate, CompanyMemberRoleUpdate
from app.security import require_active_company_membership, require_company_admin, get_current_profile
from app.services.deletion import process_employee_deletion_queue
from app.services.clerk_client import update_organization_membership, ClerkAPIError

router = APIRouter(prefix="/companies/{company_id}/members", tags=["company-members"])

# NOTE: inviting new members is handled by Clerk's own organization-invite
# UI/API (per README: "Brand Admins invite employees via email using Clerk's
# organization management features"). The corresponding company_members row
# is created here automatically by the organizationMembership.created
# webhook (see app/routers/clerk_webhooks.py) — there's no direct "create
# member" endpoint in this API.


async def _revoke_owner_role_if_needed(
    profile_id: str,
    current_company_id: uuid.UUID,
    db: AsyncSession,
    profile: "Profile | None" = None,
):
    """
    If a user is no longer an active OWNER in this company, check if they are an OWNER
    in any OTHER active company. If not, revoke their global BRAND_ADMIN system role.
    Accepts an optional pre-fetched (and already locked) profile to avoid a redundant query.
    """
    if profile is None:
        profile_res = await db.execute(select(Profile).where(Profile.id == profile_id).with_for_update())
        profile = profile_res.scalar_one_or_none()
    
    if profile and profile.system_role == SystemRole.BRAND_ADMIN:
        result = await db.execute(
            select(
                select(CompanyMember)
                .join(Company, Company.id == CompanyMember.company_id)
                .where(
                    CompanyMember.profile_id == profile_id,
                    CompanyMember.member_role == MemberRole.OWNER,
                    CompanyMember.status == MemberStatus.ACTIVE,
                    CompanyMember.company_id != current_company_id,
                    Company.deleted_at.is_(None),
                )
                .exists()
            )
        )
        is_owner_elsewhere = result.scalar()
        
        if not is_owner_elsewhere:
            profile.system_role = SystemRole.BRAND_EMPLOYEE


@router.get("", response_model=list[CompanyMemberOut])
async def list_members(
    company_id: uuid.UUID,
    _membership: CompanyMember = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    if _membership.id is not None:
        member_res = await db.execute(
            select(CompanyMember.member_role).where(
                CompanyMember.id == _membership.id,
                CompanyMember.status == MemberStatus.ACTIVE
            )
        )
        fresh_role = member_res.scalar_one_or_none()
        if fresh_role is None or fresh_role != MemberRole.OWNER:
            raise HTTPException(status_code=403, detail="Admin privileges revoked")

    result = await db.execute(select(CompanyMember).where(CompanyMember.company_id == company_id))
    return result.scalars().all()


@router.patch("/{profile_id}/status", response_model=CompanyMemberOut)
async def update_member_status(
    company_id: uuid.UUID,
    profile_id: str,
    body: CompanyMemberStatusUpdate,
    _admin_membership: CompanyMember = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin-only: suspend/reinstate/terminate a member. Per README, status
    changes take effect immediately (access is checked live via
    require_active_company_membership on every request).
    """
    # Serialize concurrent admin actions for this company to prevent deadlocks
    await db.execute(select(Company.id).where(Company.id == company_id).with_for_update())

    # Pre-lock Profile to respect global lock hierarchy (Company -> Profile -> CompanyMember)
    # This prevents deadlocks with clerk_webhooks.py which locks Profile -> CompanyMember
    await db.execute(select(Profile.id).where(Profile.id == profile_id).with_for_update())

    # Prevent TOCTOU on admin privileges
    if _admin_membership.id is not None:
        recheck = await db.execute(
            select(CompanyMember).where(
                CompanyMember.id == _admin_membership.id,
                CompanyMember.status == MemberStatus.ACTIVE,
                CompanyMember.member_role == MemberRole.OWNER
            ).with_for_update()
        )
        if not recheck.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Admin privileges revoked during request")

    if body.status not in (MemberStatus.ACTIVE, MemberStatus.SUSPENDED, MemberStatus.TERMINATED):
        raise HTTPException(status_code=400, detail="Invalid status transition")

    result = await db.execute(
        select(CompanyMember).where(
            CompanyMember.profile_id == profile_id, 
            CompanyMember.company_id == company_id
        ).with_for_update()
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found in this company")
    
    if member.status == MemberStatus.DELETING:
        raise HTTPException(status_code=400, detail="Cannot modify a member that is being deleted")

    if member.member_role == MemberRole.OWNER and body.status in (MemberStatus.SUSPENDED, MemberStatus.TERMINATED):
        owners_result = await db.execute(
            select(CompanyMember).where(
                CompanyMember.company_id == company_id,
                CompanyMember.member_role == MemberRole.OWNER,
                CompanyMember.status == MemberStatus.ACTIVE
            ).with_for_update()
        )
        active_owners = owners_result.scalars().all()
        if len(active_owners) <= 1 and any(o.id == member.id for o in active_owners):
            raise HTTPException(status_code=400, detail="Cannot suspend or terminate the only active admin.")

    was_active = (member.status == MemberStatus.ACTIVE)
    member.status = body.status
    
    if member.member_role == MemberRole.OWNER:
        if body.status in (MemberStatus.SUSPENDED, MemberStatus.TERMINATED):
            # Profile already locked on line 91; pass it in to avoid a second round-trip
            profile_res = await db.execute(select(Profile).where(Profile.id == profile_id).with_for_update())
            locked_profile = profile_res.scalar_one_or_none()
            await _revoke_owner_role_if_needed(profile_id, company_id, db, profile=locked_profile)
        elif body.status == MemberStatus.ACTIVE and not was_active:
            profile_res = await db.execute(select(Profile).where(Profile.id == profile_id).with_for_update())
            profile = profile_res.scalar_one_or_none()
            if profile and profile.system_role == SystemRole.BRAND_EMPLOYEE:
                profile.system_role = SystemRole.BRAND_ADMIN

    await db.commit()
    await db.refresh(member)
    return member

@router.patch("/{profile_id}/role", response_model=CompanyMemberOut)
async def update_member_role(
    company_id: uuid.UUID,
    profile_id: str,
    body: CompanyMemberRoleUpdate,
    _admin_membership: CompanyMember = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin-only: promote/demote a member (change role)."""
    # Serialize concurrent admin actions for this company
    result_company = await db.execute(select(Company).where(Company.id == company_id).with_for_update())
    company = result_company.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Lock Profile to respect global lock hierarchy
    profile_res = await db.execute(select(Profile).where(Profile.id == profile_id).with_for_update())
    profile = profile_res.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    if _admin_membership.id is not None:
        recheck = await db.execute(
            select(CompanyMember).where(
                CompanyMember.id == _admin_membership.id,
                CompanyMember.status == MemberStatus.ACTIVE,
                CompanyMember.member_role == MemberRole.OWNER
            ).with_for_update()
        )
        if not recheck.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Admin privileges revoked during request")

    result = await db.execute(
        select(CompanyMember).where(
            CompanyMember.profile_id == profile_id, 
            CompanyMember.company_id == company_id
        ).with_for_update()
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found in this company")
    
    if member.status != MemberStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Cannot change role of a non-active member")

    if member.member_role == MemberRole.OWNER and body.member_role == MemberRole.MEMBER:
        owners_result = await db.execute(
            select(CompanyMember).where(
                CompanyMember.company_id == company_id,
                CompanyMember.member_role == MemberRole.OWNER,
                CompanyMember.status == MemberStatus.ACTIVE
            ).with_for_update()
        )
        active_owners = owners_result.scalars().all()
        if len(active_owners) <= 1 and any(o.id == member.id for o in active_owners):
            raise HTTPException(status_code=400, detail="Cannot demote the only active admin.")


    # Make Clerk API call first
    # Map backend roles to Clerk roles (Clerk uses "org:admin" and "org:member")
    clerk_role = "org:admin" if body.member_role == MemberRole.OWNER else "org:member"
    try:
        await update_organization_membership(company.clerk_org_id, profile_id, clerk_role)
    except ClerkAPIError as e:
        raise HTTPException(status_code=500, detail=f"Failed to update role in Clerk: {e}")

    # Update local DB role
    member.member_role = body.member_role

    if body.member_role == MemberRole.OWNER:
        if profile and profile.system_role == SystemRole.BRAND_EMPLOYEE:
            profile.system_role = SystemRole.BRAND_ADMIN
    elif body.member_role == MemberRole.MEMBER:
        # profile already locked above; pass it in to skip the redundant re-query
        await _revoke_owner_role_if_needed(profile_id, company_id, db, profile=profile)

    await db.commit()
    await db.refresh(member)
    return member

@router.delete("/{profile_id}", status_code=status.HTTP_202_ACCEPTED)
async def delete_member(
    company_id: uuid.UUID,
    profile_id: str,
    background_tasks: BackgroundTasks,
    promote_profile_id: str | None = None,
    current_profile: Profile = Depends(get_current_profile),
    db: AsyncSession = Depends(get_db),
):
    # Serialize concurrent admin actions for this company to prevent deadlocks
    result_company = await db.execute(select(Company).where(Company.id == company_id).with_for_update())
    company = result_company.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Check permissions INSIDE the lock to prevent TOCTOU
    if current_profile.system_role != SystemRole.PLATFORM_ADMIN:
        membership_res = await db.execute(
            select(CompanyMember)
            .join(Company, Company.id == CompanyMember.company_id)
            .where(
                CompanyMember.company_id == company_id,
                CompanyMember.profile_id == current_profile.id,
                CompanyMember.status == MemberStatus.ACTIVE,
                Company.deleted_at.is_(None)
            ).with_for_update()
        )
        current_membership = membership_res.scalar_one_or_none()
        if not current_membership:
            raise HTTPException(status_code=403, detail="Not an active member of this company")

        if current_profile.id != profile_id and current_membership.member_role != MemberRole.OWNER:
            raise HTTPException(status_code=403, detail="Not authorized to delete this member")

    # Validate promote_profile_id exists before acquiring any row locks,
    # to avoid locking rows for profiles that don't exist (DoS amplification).
    if promote_profile_id:
        valid_promote = await db.scalar(select(Profile.id).where(Profile.id == promote_profile_id))
        if not valid_promote:
            raise HTTPException(status_code=400, detail="promote_profile_id does not match any profile")

    # Sort and lock profiles lexicographically to prevent cross-company deadlocks
    profile_ids_to_lock = sorted([p for p in (profile_id, promote_profile_id) if p])
    for pid in profile_ids_to_lock:
        await db.execute(select(Profile.id).where(Profile.id == pid).with_for_update())

    # Fetch the member to delete
    result = await db.execute(
        select(CompanyMember).where(
            CompanyMember.company_id == company_id, 
            CompanyMember.profile_id == profile_id,
            CompanyMember.status != MemberStatus.DELETING
        ).with_for_update()
    )
    target_member = result.scalar_one_or_none()
    if target_member is None:
        raise HTTPException(status_code=404, detail="Member not found")

    # If an OWNER is deleting themselves, check if they are the only OWNER
    if target_member.member_role == MemberRole.OWNER:
        owners_result = await db.execute(
            select(CompanyMember).where(
                CompanyMember.company_id == company_id,
                CompanyMember.member_role == MemberRole.OWNER,
                CompanyMember.status == MemberStatus.ACTIVE
            ).with_for_update()
        )
        active_owners = owners_result.scalars().all()
        owner_count = len(active_owners)
        
        is_target_active_owner = target_member.status == MemberStatus.ACTIVE
        if is_target_active_owner and owner_count <= 1:
            if not promote_profile_id or promote_profile_id == profile_id:
                raise HTTPException(
                    status_code=400, 
                    detail="Cannot delete the only admin. Please provide a different promote_profile_id to promote another member."
                )
            
            # Promote the other user
            promote_result = await db.execute(
                select(CompanyMember).where(
                    CompanyMember.company_id == company_id,
                    CompanyMember.profile_id == promote_profile_id,
                    CompanyMember.status == MemberStatus.ACTIVE
                ).with_for_update()
            )
            promoted_member = promote_result.scalar_one_or_none()
            if not promoted_member:
                raise HTTPException(status_code=400, detail="Promoted user is not an active member")
            
            promoted_member.member_role = MemberRole.OWNER
            
            try:
                await update_organization_membership(company.clerk_org_id, promote_profile_id, "org:admin")
            except ClerkAPIError as e:
                raise HTTPException(status_code=500, detail=f"Failed to promote user in Clerk: {e}")
                
            # promoted_profile already locked above in the sorted profile lock block
            promoted_profile_res = await db.execute(
                select(Profile).where(Profile.id == promote_profile_id)
            )
            promoted_profile = promoted_profile_res.scalar_one_or_none()
            if promoted_profile and promoted_profile.system_role == SystemRole.BRAND_EMPLOYEE:
                promoted_profile.system_role = SystemRole.BRAND_ADMIN

    # Mark as deleting
    target_member.status = MemberStatus.DELETING
    
    if target_member.member_role == MemberRole.OWNER:
        # Fetch the target's profile (already locked in the sorted loop above)
        target_profile_res = await db.execute(select(Profile).where(Profile.id == profile_id))
        target_profile = target_profile_res.scalar_one_or_none()
        await _revoke_owner_role_if_needed(profile_id, company_id, db, profile=target_profile)

    await db.commit()

    # Background task
    background_tasks.add_task(process_employee_deletion_queue, company_id, profile_id)
    return {"message": "Member deletion started"}
