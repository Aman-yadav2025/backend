import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Company, CompanyMember, Payment, PaymentStatus, Profile, PromoCode, RefundRequest, RefundRequestStatus, MemberRole, MemberStatus
from app.pricing import get_price_for
from app.schemas import CheckoutRequest, CheckoutResponse, PaymentOut, PaymentVerifyRequest, RefundRequestCreate, RefundRequestOut
from app.security import get_current_profile, require_company_admin
from app.services import razorpay_client

router = APIRouter(prefix="/companies/{company_id}/payments", tags=["payments"])


async def _lock_and_apply_promo(db: AsyncSession, code: str, company_id: uuid.UUID) -> PromoCode:
    """Row-locks the promo code for the duration of THIS transaction and
    increments its usage immediately, atomically with the payment row
    being created in the same commit — see razorpay_webhooks.py for why
    a webhook-time-only lock can't actually prevent over-redemption.
    Caller MUST db.rollback() on any later failure to release this lock.
    """
    result = await db.execute(select(PromoCode).where(PromoCode.code == code).with_for_update())
    promo = result.scalar_one_or_none()

    if promo is None:
        raise HTTPException(status_code=400, detail="Promo code does not exist")
    if promo.assigned_company_id is not None and promo.assigned_company_id != company_id:
        raise HTTPException(status_code=400, detail="Promo code is not valid for this company")
    if not promo.is_active:
        raise HTTPException(status_code=400, detail="Promo code is not active")

    now = datetime.now(timezone.utc)
    if now < promo.valid_from or now > promo.valid_until:
        raise HTTPException(status_code=400, detail="Promo code is outside its valid date range")
    if promo.current_uses >= promo.max_uses:
        raise HTTPException(status_code=400, detail="Promo code has reached its usage limit")

    promo.current_uses += 1
    return promo


def _compute_discount(promo: PromoCode, original_amount: float) -> float:
    if promo.discount_type.value == "PERCENTAGE":
        return round(original_amount * float(promo.discount_value) / 100, 2)
    return min(float(promo.discount_value), original_amount)  # FIXED_AMOUNT, never exceeds the bill


@router.post("/checkout", response_model=CheckoutResponse)
async def initiate_checkout(
    company_id: uuid.UUID,
    body: CheckoutRequest,
    admin_member: CompanyMember = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    # NEW: checkout can target a DIFFERENT plan than the company's current
    # one (an upgrade/downgrade) — if omitted, defaults to current
    # pack/tier (a same-plan renewal). This is now the ONLY way pack/tier
    # can change after initial /plan setup — see companies.py's plan lock.
    target_pack = body.plan_package if body.plan_package is not None else company.pack
    target_tier = body.plan_tier if body.plan_tier is not None else company.tier

    original_amount = get_price_for(target_pack, target_tier)
    discount_amount = 0.0
    promo: PromoCode | None = None

    if body.promo_code:
        promo = await _lock_and_apply_promo(db, body.promo_code, company_id)
        discount_amount = _compute_discount(promo, original_amount)

    amount_paid = round(original_amount - discount_amount, 2)

    if amount_paid <= 0:
        fake_order_id = f"free_order_{uuid.uuid4().hex[:16]}"
        payment = Payment(
            company_id=company_id,
            initiated_by_profile_id=admin_member.profile_id,
            razorpay_order_id=fake_order_id,
            status=PaymentStatus.SUCCESS,
            original_amount=original_amount,
            discount_amount=discount_amount,
            amount_paid=0.0,
            currency="INR",
            applied_promo_id=promo.id if promo else None,
            plan_package=target_pack,
            plan_tier=target_tier,
        )
        db.add(payment)
        await _apply_plan_on_success(db, payment)
        await db.commit()
        await db.refresh(payment)

        return CheckoutResponse(
            payment_id=payment.id,
            razorpay_order_id=fake_order_id,
            razorpay_key_id="free",
            amount_paid=0.0,
            currency="INR",
        )

    try:
        order = await razorpay_client.create_order(
            amount_in_rupees=amount_paid,
            currency="INR",
            receipt=f"company_{company_id}_{uuid.uuid4().hex[:10]}",
            notes={
                "company_id": str(company_id),
                "pack": target_pack.value,
                "tier": str(target_tier),
                "promo_code": body.promo_code or "",
            },
        )
    except Exception as exc:  # noqa: BLE001
        await db.rollback()  # releases the promo lock if one was taken
        raise HTTPException(status_code=502, detail=f"Razorpay order creation failed: {exc}") from exc

    payment = Payment(
        company_id=company_id,
        initiated_by_profile_id=admin_member.profile_id,
        razorpay_order_id=order["id"],
        status=PaymentStatus.PENDING,
        original_amount=original_amount,
        discount_amount=discount_amount,
        amount_paid=amount_paid,
        currency="INR",
        applied_promo_id=promo.id if promo else None,
        plan_package=target_pack,
        plan_tier=target_tier,
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)

    return CheckoutResponse(
        payment_id=payment.id,
        razorpay_order_id=order["id"],
        razorpay_key_id=settings.razorpay_key_id,
        amount_paid=amount_paid,
        currency="INR",
    )


async def _apply_plan_on_success(db: AsyncSession, payment: Payment) -> None:
    """Shared by both /verify and the webhook, since either can be the
    first to flip a payment to SUCCESS — see the idempotency comment in
    each caller. Locks the company row so this can't race with itself if
    somehow both paths fire near-simultaneously.
    """
    result = await db.execute(select(Company).where(Company.id == payment.company_id).with_for_update())
    company = result.scalar_one_or_none()
    if company is not None:
        company.pack = payment.plan_package
        company.tier = payment.plan_tier


@router.post("/verify", response_model=PaymentOut)
async def verify_payment(
    company_id: uuid.UUID,
    body: PaymentVerifyRequest,
    admin_member: CompanyMember = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    """Fast client-side confirmation path. NOT the source of truth — the
    webhook is — but since either can be first to mark SUCCESS, both must
    independently apply the plan change on that transition (idempotent:
    the webhook's own SUCCESS-guard means this only ever runs once per
    payment, from whichever path gets there first).
    """
    result = await db.execute(
        select(Payment).where(
            Payment.razorpay_order_id == body.razorpay_order_id, Payment.company_id == company_id
        ).with_for_update()
    )
    payment = result.scalar_one_or_none()
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")

    if not razorpay_client.verify_payment_signature(
        body.razorpay_order_id, body.razorpay_payment_id, body.razorpay_signature
    ):
        raise HTTPException(status_code=400, detail="Signature verification failed")

    if payment.status == PaymentStatus.PENDING:
        payment.razorpay_payment_id = body.razorpay_payment_id
        payment.razorpay_signature = body.razorpay_signature
        payment.status = PaymentStatus.SUCCESS
        await _apply_plan_on_success(db, payment)
        await db.commit()
        await db.refresh(payment)

    return payment


@router.get("", response_model=list[PaymentOut])
async def list_payments(
    company_id: uuid.UUID,
    admin_member: CompanyMember = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Payment).where(Payment.company_id == company_id))
    return result.scalars().all()


@router.post("/{payment_id}/refund-request", response_model=RefundRequestOut, status_code=201)
async def request_refund(
    company_id: uuid.UUID,
    payment_id: uuid.UUID,
    body: RefundRequestCreate,
    admin_member: CompanyMember = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Payment).where(Payment.id == payment_id, Payment.company_id == company_id).with_for_update()
    )
    payment = result.scalar_one_or_none()
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")

    if admin_member.id is not None:
        recheck = await db.execute(
            select(CompanyMember).where(
                CompanyMember.id == admin_member.id,
                CompanyMember.status == MemberStatus.ACTIVE,
                CompanyMember.member_role == MemberRole.OWNER
            )
        )
        if not recheck.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Admin privileges revoked during request")

    if payment.status not in (PaymentStatus.SUCCESS, PaymentStatus.PARTIALLY_REFUNDED, PaymentStatus.PENDING_REFUND):
        raise HTTPException(status_code=400, detail="This payment cannot be refunded")

    existing_refunds = await db.execute(
        select(func.sum(RefundRequest.amount))
        .where(RefundRequest.payment_id == payment.id)
        .where(RefundRequest.status != RefundRequestStatus.REJECTED)
    )
    total_refunded_val = existing_refunds.scalar()
    total_refunded = Decimal(str(total_refunded_val)) if total_refunded_val is not None else Decimal("0.00")

    if body.amount + total_refunded > Decimal(str(payment.amount_paid)):
        raise HTTPException(status_code=400, detail="Total refund requests exceed amount paid")

    refund_request = RefundRequest(
        payment_id=payment.id,
        requested_by_profile_id=admin_member.profile_id,
        amount=body.amount,
    )
    db.add(refund_request)

    payment.status = PaymentStatus.PENDING_REFUND

    await db.commit()
    await db.refresh(refund_request)
    return refund_request
