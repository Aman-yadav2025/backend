from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from svix.webhooks import Webhook, WebhookVerificationError
import uuid

from app.config import settings
from app.database import get_db
from app.models import Company, CompanyMember, CompanyType, MemberRole, MemberStatus, PackType, Profile, SystemRole

router = APIRouter(prefix="/webhooks/clerk", tags=["clerk-webhooks"])


@router.post("")
async def handle_clerk_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.body()

    wh = Webhook(settings.clerk_webhook_secret.get_secret_value())
    try:
        event = wh.verify(payload, dict(request.headers))
    except WebhookVerificationError as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook signature") from exc

    event_type = event.get("type")
    data = event.get("data", {})

    if event_type in ("user.created", "user.updated"):
        await _upsert_profile(db, data)

    elif event_type == "user.deleted":
        await _handle_user_deleted(db, data)

    elif event_type == "organization.created":
        await _create_company_from_org(db, data)

    elif event_type == "organizationMembership.created":
        await _upsert_company_member(db, data, forced_status=MemberStatus.ACTIVE)

    elif event_type == "organizationMembership.updated":
        await _upsert_company_member(db, data, forced_status=None)

    elif event_type == "organizationMembership.deleted":
        await _deactivate_company_member(db, data)

    else:
        # Unhandled event types are ignored, not errors — Clerk sends many
        # event types we don't care about (sessions, invitations, etc.)
        return {"received": True, "handled": False}

    await db.commit()
    return {"received": True, "handled": True}


async def _upsert_profile(db: AsyncSession, data: dict) -> None:
    clerk_user_id = data["id"]
    email_addresses = data.get("email_addresses", [])
    primary_email_id = data.get("primary_email_address_id")

    email = next(
        (e["email_address"] for e in email_addresses if e["id"] == primary_email_id),
        email_addresses[0]["email_address"] if email_addresses else None,
    )
    if not email:
        raise HTTPException(status_code=400, detail="Clerk user event has no email address")

    result = await db.execute(select(Profile).where(Profile.id == clerk_user_id))
    profile = result.scalar_one_or_none()

    if profile is None:
        # Default role at signup. Promoted to BRAND_ADMIN when they create an
        # organization (see _create_company_from_org), or set to whatever the
        # organizationMembership role maps to when invited into one.
        db.add(Profile(id=clerk_user_id, email=email, system_role=SystemRole.BRAND_EMPLOYEE))
    else:
        profile.email = email


async def _handle_user_deleted(db: AsyncSession, data: dict) -> None:
    # Clerk can send "id": null in user.deleted payloads (e.g. test/dev deletions).
    # Without this guard, every WHERE clause silently matches nothing.
    clerk_user_id = data.get("id")
    if not clerk_user_id:
        return

    # 1. Soft-delete any companies owned by this user (Locks Company first)
    from sqlalchemy import select, func, delete, update
    companies_res = await db.execute(select(Company).where(Company.owner_id == clerk_user_id, Company.deleted_at.is_(None)).with_for_update())
    for comp in companies_res.scalars().all():
        comp.deleted_at = func.now()
        
    # CRITICAL: Flush the company soft-deletes to the outer transaction NOW.
    # Otherwise, they are pushed during the savepoint and lost when the savepoint rolls back!
    await db.flush()

    # 2. Acquire a lock on Profile
    profile_res = await db.execute(select(Profile).where(Profile.id == clerk_user_id).with_for_update())
    profile = profile_res.scalar_one_or_none()

    # 3. Strip access to all companies (fixes 60s JWT bug)
    await db.execute(delete(CompanyMember).where(CompanyMember.profile_id == clerk_user_id))
    
    # 4. Attempt to hard delete profile
    if profile:
        try:
            # Use a savepoint to catch IntegrityError without breaking the outer transaction
            async with db.begin_nested():
                await db.delete(profile)
                await db.flush()
        except IntegrityError:
            # 5. Financial Fallback (RESTRICT): Scramble email to free it up for re-registration
            # Use a core update because the savepoint rollback expired the ORM session objects.
            await db.execute(
                update(Profile)
                .where(Profile.id == clerk_user_id)
                .values(email=f"deleted_{uuid.uuid4()}@deleted.local")
            )


async def _create_company_from_org(db: AsyncSession, data: dict) -> None:
    clerk_org_id = data["id"]
    name = data.get("name") or "Unnamed Company"
    created_by = data.get("created_by")

    if not created_by:
        raise HTTPException(status_code=400, detail="organization.created event missing created_by")

    result = await db.execute(select(Profile).where(Profile.id == created_by).with_for_update())
    owner_profile = result.scalar_one_or_none()
    if owner_profile is None:
        # user.created should normally arrive first; if Clerk delivers these
        # out of order, returning 400 makes Clerk retry the webhook shortly.
        raise HTTPException(status_code=400, detail="Org creator has no profile yet; will retry")

    if owner_profile.system_role == SystemRole.BRAND_EMPLOYEE:
        owner_profile.system_role = SystemRole.BRAND_ADMIN

    # NOTE: default company_type/pack/tier below are placeholders — the
    # README doesn't yet specify how a brand-new org picks its type/pack/tier
    # (e.g. a signup-flow question, or a separate onboarding endpoint). Flag
    # this if STARTER/tier 1/BRAND isn't the right default.
    company = Company(
        clerk_org_id=clerk_org_id,
        owner_id=owner_profile.id,
        name=name,
        company_type=CompanyType.BRAND,
        pack=PackType.STARTER,
        tier=1,
    )
    db.add(company)
    await db.flush()  # populate company.id for the membership row below

    db.add(
        CompanyMember(
            company_id=company.id,
            profile_id=owner_profile.id,
            member_role=MemberRole.OWNER,
            status=MemberStatus.ACTIVE,
        )
    )


async def _get_company_by_clerk_org_id(db: AsyncSession, clerk_org_id: str) -> Company:
    result = await db.execute(select(Company).where(Company.clerk_org_id == clerk_org_id).with_for_update())
    company = result.scalar_one_or_none()
    if company is None:
        raise HTTPException(status_code=400, detail="Company not found for this organization; will retry")
    return company


async def _upsert_company_member(db: AsyncSession, data: dict, forced_status: MemberStatus | None) -> None:
    clerk_org_id = data["organization"]["id"]
    clerk_user_id = data["public_user_data"]["user_id"]
    clerk_role = data.get("role", "")  # e.g. "org:admin" / "org:member"

    company = await _get_company_by_clerk_org_id(db, clerk_org_id)

    # 1. Lock Profile first to respect global lock hierarchy (Company -> Profile -> CompanyMember)
    profile_res = await db.execute(select(Profile).where(Profile.id == clerk_user_id).with_for_update())
    profile = profile_res.scalar_one_or_none()

    # Profile was deleted by a concurrent user.deleted webhook or DELETE /profiles/me.
    # There is nothing to do — the user is gone. Return 200 so Clerk does not retry forever.
    if profile is None:
        return

    # 2. Lock CompanyMember second
    result = await db.execute(
        select(CompanyMember).where(
            CompanyMember.company_id == company.id,
            CompanyMember.profile_id == clerk_user_id,
        ).with_for_update()
    )
    member = result.scalar_one_or_none()

    member_role = MemberRole.OWNER if "admin" in clerk_role else MemberRole.MEMBER
    resolved_status = forced_status or MemberStatus.ACTIVE
    
    was_owner = False
    if member is None:
        db.add(
            CompanyMember(
                company_id=company.id,
                profile_id=clerk_user_id,
                member_role=member_role,
                status=resolved_status,
            )
        )
    else:
        was_owner = (member.member_role == MemberRole.OWNER)
        member.member_role = member_role
        member.status = resolved_status

    # Keep the invited employee's system_role in sync with their org role.
    if profile is not None:
        if profile.system_role == SystemRole.BRAND_EMPLOYEE and member_role == MemberRole.OWNER and company.deleted_at is None:
            profile.system_role = SystemRole.BRAND_ADMIN
        elif profile.system_role == SystemRole.BRAND_ADMIN and was_owner and (member_role != MemberRole.OWNER or resolved_status != MemberStatus.ACTIVE):
            is_owner_elsewhere_res = await db.execute(
                select(
                    select(CompanyMember)
                    .join(Company, Company.id == CompanyMember.company_id)
                    .where(
                        CompanyMember.profile_id == clerk_user_id,
                        CompanyMember.member_role == MemberRole.OWNER,
                        CompanyMember.status == MemberStatus.ACTIVE,
                        CompanyMember.company_id != company.id,
                        Company.deleted_at.is_(None)
                    )
                    .exists()
                )
            )
            if not is_owner_elsewhere_res.scalar():
                profile.system_role = SystemRole.BRAND_EMPLOYEE


async def _deactivate_company_member(db: AsyncSession, data: dict) -> None:
    clerk_org_id = data["organization"]["id"]
    clerk_user_id = data["public_user_data"]["user_id"]

    company = await _get_company_by_clerk_org_id(db, clerk_org_id)

    # 1. Lock Profile first to respect global lock hierarchy
    profile_res = await db.execute(select(Profile).where(Profile.id == clerk_user_id).with_for_update())
    profile = profile_res.scalar_one_or_none()

    # 2. Lock CompanyMember second
    result = await db.execute(
        select(CompanyMember).where(
            CompanyMember.company_id == company.id,
            CompanyMember.profile_id == clerk_user_id,
        ).with_for_update()
    )
    member = result.scalar_one_or_none()
    if member is not None:
        was_owner = (member.member_role == MemberRole.OWNER)
        member.status = MemberStatus.TERMINATED
        
        if was_owner:
            if profile and profile.system_role == SystemRole.BRAND_ADMIN:
                is_owner_elsewhere_res = await db.execute(
                    select(
                        select(CompanyMember)
                        .join(Company, Company.id == CompanyMember.company_id)
                        .where(
                            CompanyMember.profile_id == clerk_user_id,
                            CompanyMember.member_role == MemberRole.OWNER,
                            CompanyMember.status == MemberStatus.ACTIVE,
                            CompanyMember.company_id != company.id,
                            Company.deleted_at.is_(None)
                        )
                        .exists()
                    )
                )
                if not is_owner_elsewhere_res.scalar():
                    profile.system_role = SystemRole.BRAND_EMPLOYEE
