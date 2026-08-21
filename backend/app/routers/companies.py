import uuid

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Company, CompanyMember, MemberRole, MemberStatus, Profile, SystemRole, Payment, Document, PaymentStatus, PackType
from app.schemas import CompanyOut, CompanyEmployeeOut, CompanyPlanUpdate, CompanyUpdate
from app.security import get_current_profile, require_company_admin, require_platform_admin, require_active_company_membership
from app.services.deletion import process_company_deletion_queue

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("/me", response_model=list[CompanyOut | CompanyEmployeeOut])
async def list_my_companies(
    profile: Profile = Depends(get_current_profile),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Company, CompanyMember.member_role)
        .join(CompanyMember, CompanyMember.company_id == Company.id)
        .where(
            CompanyMember.profile_id == profile.id,
            CompanyMember.status == MemberStatus.ACTIVE,
            Company.deleted_at.is_(None)
        )
    )
    
    companies = []
    for company, role in result.all():
        if role == MemberRole.OWNER:
            companies.append(CompanyOut.model_validate(company))
        else:
            companies.append(CompanyEmployeeOut.model_validate(company))
            
    return companies


@router.get("/{company_id}", response_model=CompanyOut | CompanyEmployeeOut)
async def get_company(
    company_id: uuid.UUID,
    _membership: CompanyMember = Depends(require_active_company_membership),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Company).where(
            Company.id == company_id,
            Company.deleted_at.is_(None)
        )
    )
    company = result.scalar_one_or_none()
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
        
    member_role = _membership.member_role
    if _membership.id is not None:
        member_res = await db.execute(
            select(CompanyMember.member_role).where(
                CompanyMember.id == _membership.id,
                CompanyMember.status == MemberStatus.ACTIVE
            )
        )
        fresh_role = member_res.scalar_one_or_none()
        if fresh_role is None:
            raise HTTPException(status_code=403, detail="Membership revoked")
        member_role = fresh_role
        
    if member_role == MemberRole.OWNER:
        return CompanyOut.model_validate(company)
    return CompanyEmployeeOut.model_validate(company)


@router.patch("/{company_id}", response_model=CompanyOut)
async def update_company(
    company_id: uuid.UUID,
    body: CompanyUpdate,
    _membership: CompanyMember = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Company).where(
            Company.id == company_id,
            Company.deleted_at.is_(None)
        ).with_for_update()
    )
    company = result.scalar_one_or_none()
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    if _membership.id is not None:
        recheck = await db.execute(
            select(CompanyMember).where(
                CompanyMember.id == _membership.id,
                CompanyMember.status == MemberStatus.ACTIVE,
                CompanyMember.member_role == MemberRole.OWNER
            ).with_for_update()
        )
        if not recheck.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Admin privileges revoked during request")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(company, field, value)

    await db.commit()
    await db.refresh(company)
    return company


@router.patch("/{company_id}/plan", response_model=CompanyOut)
async def update_company_plan(
    company_id: uuid.UUID,
    body: CompanyPlanUpdate,
    _membership: CompanyMember = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Onboarding-only endpoint. Sets company_type/pack/tier the FIRST time,
    right after signup. Once the company has any activity (a payment or a
    document), this endpoint can no longer change ANY of company_type,
    pack, or tier — not just company_type as before. After that point,
    the only way to change pack/tier is by completing a real payment via
    POST /companies/{id}/payments/checkout (which now accepts an optional
    plan_package/plan_tier to upgrade/downgrade to, and updates the
    company's stored pack/tier on successful payment). company_type
    itself can never change after activity, by design — there's no
    payment-driven path for that, since it represents what kind of
    business this is, not a purchasable plan.
    """
    result = await db.execute(
        select(Company).where(
            Company.id == company_id,
            Company.deleted_at.is_(None)
        ).with_for_update()
    )
    company = result.scalar_one_or_none()
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    if _membership.id is not None:
        recheck = await db.execute(
            select(CompanyMember).where(
                CompanyMember.id == _membership.id,
                CompanyMember.status == MemberStatus.ACTIVE,
                CompanyMember.member_role == MemberRole.OWNER
            ).with_for_update()
        )
        if not recheck.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Admin privileges revoked during request")

    wants_change = (
        company.company_type != body.company_type
        or company.pack != body.pack
        or company.tier != body.tier
    )

    if wants_change:
        has_activity = await db.execute(
            select(
                select(Payment).where(Payment.company_id == company_id).exists()
            )
        )
        has_payments = has_activity.scalar()

        if not has_payments:
            has_docs_activity = await db.execute(
                select(
                    select(Document).where(Document.company_id == company_id).exists()
                )
            )
            has_payments = has_payments or has_docs_activity.scalar()

        if has_payments:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Company plan is locked after initial setup and activity. "
                    "Use POST /payments/checkout with plan_package/plan_tier to change plans instead."
                ),
            )
            
        # Security Fix: Prevent upgrading to paid plans without going through the checkout flow.
        # This endpoint is only for initial onboarding (setting company_type or confirming the free plan).
        if body.pack != PackType.STARTER or body.tier > 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot upgrade to a paid plan directly. Please use the checkout flow to upgrade."
            )

    company.company_type = body.company_type
    company.pack = body.pack
    company.tier = body.tier

    await db.commit()
    await db.refresh(company)
    return company


@router.delete("/{company_id}", status_code=status.HTTP_202_ACCEPTED)
async def delete_company(
    company_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    _membership: CompanyMember = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Company).where(Company.id == company_id, Company.deleted_at.is_(None)).with_for_update())
    company = result.scalar_one_or_none()
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    if _membership.id is not None:
        recheck = await db.execute(
            select(CompanyMember).where(
                CompanyMember.id == _membership.id,
                CompanyMember.status == MemberStatus.ACTIVE,
                CompanyMember.member_role == MemberRole.OWNER
            ).with_for_update()
        )
        if not recheck.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Admin privileges revoked during request")


    payments_result = await db.execute(
        select(Payment).where(
            Payment.company_id == company_id,
            Payment.status.in_([PaymentStatus.PENDING, PaymentStatus.PENDING_REFUND, PaymentStatus.FAILED])
        )
    )
    if payments_result.first():
        raise HTTPException(status_code=400, detail="Cannot delete a brand with pending or failed payments")

    from sqlalchemy import func
    company.deleted_at = func.now()

    members_result = await db.execute(
        select(CompanyMember).where(CompanyMember.company_id == company_id).with_for_update()
    )
    members = members_result.scalars().all()
    for member in members:
        member.status = MemberStatus.DELETING

    # Revoke global roles for all owners
    owner_profile_ids = [m.profile_id for m in members if m.member_role == MemberRole.OWNER]
    if owner_profile_ids:
        # Sort to prevent deadlocks
        owner_profile_ids.sort()
        for pid in owner_profile_ids:
            profile_res = await db.execute(select(Profile).where(Profile.id == pid).with_for_update())
            profile = profile_res.scalar_one_or_none()
            if profile and profile.system_role == SystemRole.BRAND_ADMIN:
                # Check if they are owner elsewhere
                is_owner_elsewhere_res = await db.execute(
                    select(
                        select(CompanyMember)
                        .join(Company, Company.id == CompanyMember.company_id)
                        .where(
                            CompanyMember.profile_id == pid,
                            CompanyMember.member_role == MemberRole.OWNER,
                            CompanyMember.status == MemberStatus.ACTIVE,
                            CompanyMember.company_id != company_id,
                            Company.deleted_at.is_(None)
                        )
                        .exists()
                    )
                )
                if not is_owner_elsewhere_res.scalar():
                    profile.system_role = SystemRole.BRAND_EMPLOYEE

    clerk_org_id = company.clerk_org_id

    await db.commit()

    background_tasks.add_task(process_company_deletion_queue, company_id, clerk_org_id)

    return {"message": "Company deletion started"}
