import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import (
    BankAccount,
    Company,
    Document,
    DocumentStatus,
    Payment,
    PaymentStatus,
    Profile,
    RefundRequest,
    RefundRequestStatus,
    SystemRole,
    WithdrawalRequest,
    WithdrawalStatus,
)
from app.schemas import (
    BankAccountOut,
    DocumentOut,
    DocumentVerifyRequest,
    ProfileOut,
    RefundRequestOut,
    WithdrawalApproveRequest,
    WithdrawalRequestOut,
)
from app.security import require_platform_admin
from app.services import razorpay_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# List refund requests  (FIX #5: pagination)
# ---------------------------------------------------------------------------
@router.get("/refund-requests", response_model=list[RefundRequestOut])
async def list_refund_requests(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    admin: Profile = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RefundRequest)
        .order_by(RefundRequest.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Approve refund request
# (FIX #2: validate before Razorpay call)
# (FIX #3: over-refund guard under lock)
# (FIX #4: no internal error details in response)
# (FIX #6: audit trail)
# ---------------------------------------------------------------------------
@router.post("/refund-requests/{request_id}/approve", response_model=RefundRequestOut)
async def approve_refund_request(
    request_id: uuid.UUID,
    admin: Profile = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    # Lock the refund request row
    result = await db.execute(select(RefundRequest).where(RefundRequest.id == request_id).with_for_update())
    refund_req = result.scalar_one_or_none()
    if refund_req is None:
        raise HTTPException(status_code=404, detail="Refund request not found")

    if refund_req.status != RefundRequestStatus.PENDING:
        raise HTTPException(status_code=400, detail="Only pending requests can be approved")

    # Lock the payment row — serializes all concurrent approvals for the same payment
    payment_result = await db.execute(
        select(Payment).where(Payment.id == refund_req.payment_id).with_for_update()
    )
    payment = payment_result.scalar_one_or_none()

    if payment is None or not payment.razorpay_payment_id:
        raise HTTPException(status_code=400, detail="Associated payment or Razorpay payment ID missing")

    # --- FIX #3: Compute total approved refunds BEFORE calling Razorpay,
    # while the payment row lock is held. This prevents concurrent approvals
    # from both passing validation. ---
    approved_refunds = await db.execute(
        select(func.sum(RefundRequest.amount))
        .where(RefundRequest.payment_id == payment.id)
        .where(RefundRequest.status == RefundRequestStatus.APPROVED)
    )
    total_prev_approved_val = approved_refunds.scalar()
    total_prev_approved = Decimal(str(total_prev_approved_val)) if total_prev_approved_val is not None else Decimal("0.00")
    total_after_approval = total_prev_approved + Decimal(str(refund_req.amount))

    # --- FIX #2: Reject if total would exceed payment amount ---
    if total_after_approval > Decimal(str(payment.amount_paid)):
        raise HTTPException(
            status_code=400,
            detail="Total approved refunds would exceed the payment amount",
        )

    # Now it's safe to call Razorpay
    try:
        refund_result = await razorpay_client.refund_payment(
            payment_id=payment.razorpay_payment_id,
            amount_in_rupees=float(refund_req.amount),
            receipt=f"rfnd_{refund_req.id.hex[:10]}",
        )
    except Exception as exc:
        # --- FIX #4: Log full error server-side, return generic message ---
        logger.exception("Razorpay refund failed for request %s", request_id)
        raise HTTPException(
            status_code=502,
            detail="Refund processing failed. Please retry or contact support.",
        ) from exc

    # ASSUMPTION: refund_payment() returns Razorpay's raw refund object,
    # which has an "id" field (e.g. "rfnd_xxx"). I don't have your actual
    # razorpay_client.py — if refund_payment() returns something else
    # (a different shape, or nothing), adjust this line to match. If it
    # currently returns None, it needs to be changed to return the API
    # response first.
    refund_req.razorpay_refund_id = refund_result.get("id") if isinstance(refund_result, dict) else None

    refund_req.status = RefundRequestStatus.APPROVED
    # --- FIX #6: Record who approved and when ---
    refund_req.actioned_by = admin.id
    refund_req.actioned_at = datetime.now(timezone.utc)

    # Determine new payment status
    if total_after_approval >= Decimal(str(payment.amount_paid)):
        payment.status = PaymentStatus.REFUNDED
    else:
        other_pending = await db.execute(
            select(RefundRequest)
            .where(RefundRequest.payment_id == payment.id)
            .where(RefundRequest.id != request_id)
            .where(RefundRequest.status == RefundRequestStatus.PENDING)
        )
        if other_pending.first():
            payment.status = PaymentStatus.PENDING_REFUND
        else:
            payment.status = PaymentStatus.PARTIALLY_REFUNDED

    await db.commit()
    await db.refresh(refund_req)
    return refund_req


# ---------------------------------------------------------------------------
# Reject refund request
# (FIX #6: audit trail)
# (FIX #7: safer payment status reset)
# ---------------------------------------------------------------------------
@router.post("/refund-requests/{request_id}/reject", response_model=RefundRequestOut)
async def reject_refund_request(
    request_id: uuid.UUID,
    admin: Profile = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(RefundRequest).where(RefundRequest.id == request_id).with_for_update())
    refund_req = result.scalar_one_or_none()
    if refund_req is None:
        raise HTTPException(status_code=404, detail="Refund request not found")

    if refund_req.status != RefundRequestStatus.PENDING:
        raise HTTPException(status_code=400, detail="Only pending requests can be rejected")

    refund_req.status = RefundRequestStatus.REJECTED
    # --- FIX #6: Record who rejected and when ---
    refund_req.actioned_by = admin.id
    refund_req.actioned_at = datetime.now(timezone.utc)

    payment_result = await db.execute(
        select(Payment).where(Payment.id == refund_req.payment_id).with_for_update()
    )
    payment = payment_result.scalar_one_or_none()
    if payment and payment.status == PaymentStatus.PENDING_REFUND:
        other_pending = await db.execute(
            select(RefundRequest)
            .where(RefundRequest.payment_id == payment.id)
            .where(RefundRequest.id != request_id)
            .where(RefundRequest.status == RefundRequestStatus.PENDING)
        )
        if not other_pending.first():
            # No more pending requests — determine correct status based on
            # whether any refunds were actually approved.
            approved_sum_result = await db.execute(
                select(func.sum(RefundRequest.amount))
                .where(RefundRequest.payment_id == payment.id)
                .where(RefundRequest.status == RefundRequestStatus.APPROVED)
            )
            approved_sum_val = approved_sum_result.scalar()
            approved_sum = Decimal(str(approved_sum_val)) if approved_sum_val is not None else Decimal("0.00")

            # --- FIX #7: Use amount-based logic instead of existence check ---
            if approved_sum >= Decimal(str(payment.amount_paid)):
                payment.status = PaymentStatus.REFUNDED
            elif approved_sum > Decimal("0.00"):
                payment.status = PaymentStatus.PARTIALLY_REFUNDED
            else:
                payment.status = PaymentStatus.SUCCESS

    await db.commit()
    await db.refresh(refund_req)
    return refund_req


# ---------------------------------------------------------------------------
# Verify document
# (FIX #1: status restricted to VERIFIED/REJECTED via schema Literal type)
# (FIX #6: audit trail)
# ---------------------------------------------------------------------------
@router.patch("/documents/{document_id}/verify", response_model=DocumentOut)
async def verify_document(
    document_id: uuid.UUID,
    body: DocumentVerifyRequest,
    admin: Profile = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Document).where(Document.id == document_id).with_for_update())
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    document.status = DocumentStatus(body.status)
    if body.status == "REJECTED":
        document.rejection_reason = body.rejection_reason
    else:
        document.rejection_reason = None

    # --- FIX #6: Record who verified/rejected and when ---
    document.verified_by = admin.id
    document.verified_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(document)
    return document


# ---------------------------------------------------------------------------
# Promote Platform Admin
# ---------------------------------------------------------------------------
@router.post("/platform-admins/{profile_id}", response_model=ProfileOut)
async def create_platform_admin(
    profile_id: str,
    admin: Profile = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Promotes an existing profile to PLATFORM_ADMIN.
    Only an existing PLATFORM_ADMIN can perform this action.
    """
    result = await db.execute(select(Profile).where(Profile.id == profile_id).with_for_update())
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    if profile.system_role == SystemRole.PLATFORM_ADMIN:
        return profile  # Already a platform admin

    profile.system_role = SystemRole.PLATFORM_ADMIN
    
    await db.commit()
    await db.refresh(profile)
    return profile


# ---------------------------------------------------------------------------
# Admin: List all withdrawal requests
# ---------------------------------------------------------------------------
@router.get("/withdrawals", response_model=list[WithdrawalRequestOut])
async def list_withdrawal_requests(
    status: WithdrawalStatus | None = None,
    limit: int = 50,
    offset: int = 0,
    admin: Profile = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Lists all withdrawal requests across the platform.
    Optionally filter by status (PENDING, APPROVED, REJECTED).
    """
    query = select(WithdrawalRequest).order_by(WithdrawalRequest.created_at.desc())
    if status is not None:
        query = query.where(WithdrawalRequest.status == status)
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Admin: Approve a withdrawal request
# (Admin has manually paid the recycler and is logging the reference)
# ---------------------------------------------------------------------------
@router.post("/withdrawals/{withdrawal_id}/approve", response_model=WithdrawalRequestOut)
async def approve_withdrawal(
    withdrawal_id: uuid.UUID,
    body: WithdrawalApproveRequest,
    admin: Profile = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Mark a PENDING withdrawal as APPROVED.

    The admin must have already manually paid the recycler (via bank
    transfer or UPI) and provides the transaction reference (UTR/UPI ref)
    as proof. The frozen amount is permanently cleared from the recycler's
    frozen_wallet_balance.
    """
    # ── 1. Lock withdrawal row ────────────────────────────────────────────────
    withdrawal = await db.scalar(
        select(WithdrawalRequest)
        .where(WithdrawalRequest.id == withdrawal_id)
        .with_for_update()
    )
    if withdrawal is None:
        raise HTTPException(status_code=404, detail="Withdrawal request not found")
    if withdrawal.status != WithdrawalStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Only PENDING withdrawals can be approved (current status: {withdrawal.status.value}).",
        )

    # ── 2. Lock company row and clear the frozen amount ───────────────────────
    company = await db.scalar(
        select(Company).where(Company.id == withdrawal.company_id).with_for_update()
    )
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    # Safety guard: frozen balance should always cover the amount, but defend
    # against manual DB corrections that might have reduced it.
    if company.frozen_wallet_balance < withdrawal.amount:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Frozen balance (₹{company.frozen_wallet_balance:.2f}) is less than "
                f"the withdrawal amount (₹{withdrawal.amount:.2f}). "
                "Please correct the balance before approving."
            ),
        )
    if company.wallet_balance < withdrawal.amount:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Total wallet balance (₹{company.wallet_balance:.2f}) is less than "
                f"the withdrawal amount (₹{withdrawal.amount:.2f}). "
                "Please correct the balance before approving."
            ),
        )

    # The money has left the platform: remove it from both frozen and total wallet.
    company.frozen_wallet_balance -= withdrawal.amount
    company.wallet_balance -= withdrawal.amount

    # ── 3. Mark as approved ───────────────────────────────────────────────────
    withdrawal.status = WithdrawalStatus.APPROVED
    withdrawal.transaction_reference = body.transaction_reference
    withdrawal.actioned_by = admin.id
    withdrawal.actioned_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(withdrawal)
    return withdrawal


# ---------------------------------------------------------------------------
# Admin: Reject a withdrawal request
# (Funds are returned to the recycler's spendable wallet_balance)
# ---------------------------------------------------------------------------
@router.post("/withdrawals/{withdrawal_id}/reject", response_model=WithdrawalRequestOut)
async def reject_withdrawal(
    withdrawal_id: uuid.UUID,
    admin: Profile = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Reject a PENDING withdrawal and refund the amount back to the
    recycler's active wallet_balance.
    """
    # ── 1. Lock withdrawal row ────────────────────────────────────────────────
    withdrawal = await db.scalar(
        select(WithdrawalRequest)
        .where(WithdrawalRequest.id == withdrawal_id)
        .with_for_update()
    )
    if withdrawal is None:
        raise HTTPException(status_code=404, detail="Withdrawal request not found")
    if withdrawal.status != WithdrawalStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Only PENDING withdrawals can be rejected (current status: {withdrawal.status.value}).",
        )

    # ── 2. Lock company row and restore the funds ─────────────────────────────
    company = await db.scalar(
        select(Company).where(Company.id == withdrawal.company_id).with_for_update()
    )
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    # Safety guard: frozen balance should always cover the amount, but defend
    # against manual DB corrections that might have reduced it.
    if company.frozen_wallet_balance < withdrawal.amount:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Frozen balance (₹{company.frozen_wallet_balance:.2f}) is less than "
                f"the withdrawal amount (₹{withdrawal.amount:.2f}). "
                "Please correct the balance before rejecting."
            ),
        )

    # Unfreeze the amount (wallet_balance was never reduced, so we just unfreeze it)
    company.frozen_wallet_balance -= withdrawal.amount

    # ── 3. Mark as rejected ───────────────────────────────────────────────────
    withdrawal.status = WithdrawalStatus.REJECTED
    withdrawal.actioned_by = admin.id
    withdrawal.actioned_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(withdrawal)
    return withdrawal
