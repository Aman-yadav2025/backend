import logging
import uuid

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.database import AsyncSessionLocal
from app.models import Company, CompanyMember, MemberStatus
from app.services.clerk_client import ClerkAPIError, delete_organization, remove_organization_membership

logger = logging.getLogger(__name__)


async def process_company_deletion_queue(company_id: uuid.UUID, clerk_org_id: str) -> None:
    """
    Background worker for deleting an entire company. Removes the Clerk
    organization (which removes every member's access to it on Clerk's
    side in one call — no need to delete individual member accounts one
    by one), cleans up local company_members rows for this company only,
    and finally attempts to hard-delete the company row itself.

    IMPORTANT: this does NOT delete `profiles` rows. A profile represents
    a Clerk identity that may belong to OTHER companies too (the schema
    explicitly supports a profile having many company_members rows across
    different companies). Deleting a profile here would either:
      - cascade-delete that person's membership in unrelated companies
        (profiles.id has ON DELETE CASCADE from company_members), or
      - raise an unhandled IntegrityError and crash this task, if they
        own any company or uploaded any document anywhere (both are
        ON DELETE RESTRICT from profiles.id).
    Removing this company's org membership is enough; the profile row
    itself is harmless to leave in place even if this was their only
    company — it's just an identity record, not a security exposure.
    """
    async with AsyncSessionLocal() as session:
        try:
            await delete_organization(clerk_org_id)
        except ClerkAPIError as e:
            logger.error(f"Failed to delete organization {clerk_org_id} from Clerk: {e}")
            # Deliberately continue: local cleanup should still proceed
            # even if Clerk's side failed, so the company doesn't stay
            # stuck mid-deletion forever over a transient Clerk API issue.

        await session.execute(delete(CompanyMember).where(CompanyMember.company_id == company_id))
        await session.commit()

        try:
            await session.execute(delete(Company).where(Company.id == company_id))
            await session.commit()
        except IntegrityError as e:
            # Expected path: ON DELETE RESTRICT on payments (or documents,
            # promo_codes.assigned_company_id) blocks the hard delete
            # because financial/audit records must never silently vanish.
            # Leave it soft-deleted forever — this is the intended
            # fallback, not an error condition.
            logger.info(
                f"Could not hard delete company {company_id} (blocked by a RESTRICT "
                f"constraint, likely payments), leaving as soft-deleted permanently: {e}"
            )
            await session.rollback()
        except Exception as e:  # noqa: BLE001
            # Anything else IS unexpected — log loudly, don't mislabel it
            # as "probably the payments constraint".
            logger.exception(f"Unexpected error hard-deleting company {company_id}: {e}")
            await session.rollback()


async def process_employee_deletion_queue(company_id: uuid.UUID, profile_id: str) -> None:
    """
    Background worker for removing a single employee from a single
    company. Removes their Clerk ORGANIZATION MEMBERSHIP only — NOT their
    Clerk user account — since this profile may still need access to
    other companies (or other parts of the platform) they belong to.
    Deleting their whole Clerk account here would silently lock them out
    of everything, not just this company.

    Also does NOT touch the `profiles` table, for the same reasons as
    process_company_deletion_queue above.
    """
    async with AsyncSessionLocal() as session:
        # Need the Clerk org id to call the membership-removal API — the
        # caller only gives us the internal company_id (UUID), so fetch it.
        result = await session.execute(select(Company.clerk_org_id).where(Company.id == company_id))
        clerk_org_id = result.scalar_one_or_none()

        if clerk_org_id is not None:
            try:
                await remove_organization_membership(clerk_org_id, profile_id)
            except ClerkAPIError as e:
                logger.error(f"Failed to remove Clerk org membership for {profile_id}: {e}")
                # Continue with local cleanup regardless — see rationale above.
        else:
            logger.error(f"Company {company_id} has no clerk_org_id; skipping Clerk-side membership removal")

        result = await session.execute(
            select(CompanyMember).where(
                CompanyMember.company_id == company_id,
                CompanyMember.profile_id == profile_id,
            )
        )
        member = result.scalar_one_or_none()
        if member is not None:
            await session.delete(member)

        await session.commit()
