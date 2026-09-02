import uuid

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Company, CompanyMember, MemberRole, MemberStatus, Profile, SystemRole, Payment, Document, PaymentStatus, PackType, CompanyType, WalletRecharge, WalletRechargeStatus
from app.schemas import CompanyOut, CompanyEmployeeOut, CompanyPlanUpdate, CompanyUpdate, WalletRechargeCheckoutRequest, WalletRechargeCheckoutResponse, WalletRechargeVerifyRequest, WalletRechargeOut, WalletBalanceOut, CompanyEPRSetUtilized, CompanyEPROverride
from app.security import get_current_profile, require_company_admin, require_platform_admin, require_active_company_membership
from app.services import razorpay_client
from app.services.deletion import process_company_deletion_queue
from app.config import settings
from app.rate_limit import limiter

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
        # Security Fix: Prevent upgrading to paid plans without going through the checkout flow.
        # This endpoint is only for initial onboarding (setting company_type or confirming the free plan).
        # This check must come BEFORE the activity check so it always runs when wants_change is True.
        if body.pack != PackType.STARTER or body.tier > 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot upgrade to a paid plan directly. Please use the checkout flow to upgrade."
            )

        has_activity = await db.execute(
            select(
                select(Payment).where(Payment.company_id == company_id).exists()
            )
        )
        has_locked = has_activity.scalar()

        if not has_locked:
            has_docs_activity = await db.execute(
                select(
                    select(Document).where(Document.company_id == company_id).exists()
                )
            )
            has_locked = has_docs_activity.scalar()

        if has_locked:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Company plan is locked after initial setup and activity. "
                    "Use POST /payments/checkout with plan_package/plan_tier to change plans instead."
                ),
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
            Payment.status.in_([PaymentStatus.PENDING, PaymentStatus.PENDING_REFUND])
        )
    )
    if payments_result.first():
        raise HTTPException(status_code=400, detail="Cannot delete a company with pending or refunding payments")

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

    return {"message": "Company marked for deletion successfully."}


@router.get("/{company_id}/wallet", response_model=WalletBalanceOut)
async def get_wallet_balance(
    company_id: uuid.UUID,
    _membership: CompanyMember = Depends(require_active_company_membership),
    db: AsyncSession = Depends(get_db),
):
    """Returns the current wallet balance and frozen amount for the company."""
    result = await db.execute(
        select(Company).where(
            Company.id == company_id,
            Company.deleted_at.is_(None)
        )
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    if company.company_type != CompanyType.BRAND:
        raise HTTPException(status_code=403, detail="Wallet is only available for Brand companies")
    return WalletBalanceOut(
        company_id=company.id,
        wallet_balance=company.wallet_balance,
        frozen_wallet_balance=company.frozen_wallet_balance,
        available_balance=company.wallet_balance - company.frozen_wallet_balance,
    )


@router.post("/{company_id}/wallet/recharge/checkout", response_model=WalletRechargeCheckoutResponse)
@limiter.limit("10/minute")
async def wallet_recharge_checkout(
    request: Request,  # Required by SlowAPI to extract the client IP
    company_id: uuid.UUID,
    body: WalletRechargeCheckoutRequest,
    _membership: CompanyMember = Depends(require_active_company_membership),
    db: AsyncSession = Depends(get_db),
):
    """
    Initiates a Razorpay payment order to top up the company wallet.
    Returns Razorpay order details so the client can open the payment widget.
    After payment, call /wallet/recharge/verify to confirm and credit the wallet.
    """
    result = await db.execute(
        select(Company).where(
            Company.id == company_id,
            Company.deleted_at.is_(None)
        )
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    if company.company_type != CompanyType.BRAND:
        raise HTTPException(
            status_code=403,
            detail="Wallet recharge is only available for Brand companies."
        )

    try:
        order = await razorpay_client.create_order(
            amount_in_rupees=float(body.amount),
            currency="INR",
            receipt=f"wallet_{company_id}_{uuid.uuid4().hex[:10]}",
            notes={
                "company_id": str(company_id),
                "purpose": "wallet_recharge",
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Razorpay order creation failed: {exc}") from exc

    recharge = WalletRecharge(
        company_id=company_id,
        initiated_by_profile_id=_membership.profile_id,
        razorpay_order_id=order["id"],
        status=WalletRechargeStatus.PENDING.value,
        amount=body.amount,
        currency="INR",
    )
    db.add(recharge)
    await db.commit()
    await db.refresh(recharge)

    return WalletRechargeCheckoutResponse(
        recharge_id=recharge.id,
        razorpay_order_id=order["id"],
        razorpay_key_id=settings.razorpay_key_id,
        amount=body.amount,
        currency="INR",
    )


@router.post("/{company_id}/wallet/recharge/verify", response_model=WalletRechargeOut)
async def wallet_recharge_verify(
    company_id: uuid.UUID,
    body: WalletRechargeVerifyRequest,
    _membership: CompanyMember = Depends(require_active_company_membership),
    db: AsyncSession = Depends(get_db),
):
    """
    Verifies the Razorpay payment signature and credits the wallet.
    Idempotent: calling this again for an already-SUCCESS recharge is a no-op.
    """
    # Lock the recharge row to prevent concurrent verify calls racing
    result = await db.execute(
        select(WalletRecharge).where(
            WalletRecharge.razorpay_order_id == body.razorpay_order_id,
            WalletRecharge.company_id == company_id,
        ).with_for_update()
    )
    recharge = result.scalar_one_or_none()
    if recharge is None:
        raise HTTPException(status_code=404, detail="Wallet recharge record not found")

    if not razorpay_client.verify_payment_signature(
        body.razorpay_order_id, body.razorpay_payment_id, body.razorpay_signature
    ):
        raise HTTPException(status_code=400, detail="Signature verification failed")

    if recharge.status == WalletRechargeStatus.PENDING.value:
        recharge.razorpay_payment_id = body.razorpay_payment_id
        recharge.razorpay_signature = body.razorpay_signature
        recharge.status = WalletRechargeStatus.SUCCESS.value

        # Credit the wallet — lock company row to prevent concurrent balance updates
        company_result = await db.execute(
            select(Company).where(
                Company.id == company_id,
                Company.deleted_at.is_(None)
            ).with_for_update().execution_options(populate_existing=True)
        )
        company = company_result.scalar_one_or_none()
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found")
        company.wallet_balance += recharge.amount

        await db.commit()
        await db.refresh(recharge)

    return recharge


# ─── EPR Credits ─────────────────────────────────────────────────────────────

@router.patch("/{company_id}/epr/utilized", response_model=CompanyOut)
async def set_epr_credits_utilized(
    company_id: uuid.UUID,
    payload: CompanyEPRSetUtilized,
    _membership: CompanyMember = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Admin-only. Sets epr_credits_utilized for the company.
    epr_credits_available is automatically recalculated as purchased - utilized.
    """
    company = await db.scalar(
        select(Company).where(
            Company.id == company_id,
            Company.deleted_at.is_(None),
        ).with_for_update()
    )
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    if payload.epr_credits_utilized > company.epr_credits_purchased:
        raise HTTPException(
            status_code=400,
            detail=(
                f"epr_credits_utilized ({payload.epr_credits_utilized}) cannot exceed "
                f"epr_credits_purchased ({company.epr_credits_purchased})"
            ),
        )

    company.epr_credits_utilized  = payload.epr_credits_utilized
    company.epr_credits_available = company.epr_credits_purchased - payload.epr_credits_utilized

    await db.commit()
    await db.refresh(company)
    return company


@router.patch("/{company_id}/epr", response_model=CompanyOut)
async def override_epr_credits(
    company_id: uuid.UUID,
    payload: CompanyEPROverride,
    _membership: CompanyMember = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Admin-only. Directly overrides all three mutable EPR credit states:
    epr_credits_required, epr_credits_purchased, and epr_credits_utilized.
    epr_credits_available is automatically derived as purchased - utilized.
    """
    company = await db.scalar(
        select(Company).where(
            Company.id == company_id,
            Company.deleted_at.is_(None),
        ).with_for_update()
    )
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    if payload.epr_credits_utilized > payload.epr_credits_purchased:
        raise HTTPException(
            status_code=400,
            detail=(
                f"epr_credits_utilized ({payload.epr_credits_utilized}) cannot exceed "
                f"epr_credits_purchased ({payload.epr_credits_purchased})"
            ),
        )

    company.epr_credits_required  = payload.epr_credits_required
    company.epr_credits_purchased  = payload.epr_credits_purchased
    company.epr_credits_utilized   = payload.epr_credits_utilized
    company.epr_credits_available  = payload.epr_credits_purchased - payload.epr_credits_utilized

    await db.commit()
    await db.refresh(company)
    return company
