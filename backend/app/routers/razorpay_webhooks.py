import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Company, Payment, PaymentStatus, PromoCode
from app.services import razorpay_client

router = APIRouter(prefix="/webhooks/razorpay", tags=["razorpay-webhooks"])


@router.post("")
async def handle_razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(...),
    db: AsyncSession = Depends(get_db),
):
    raw_body = await request.body()

    if not razorpay_client.verify_webhook_signature(raw_body, x_razorpay_signature):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    event = json.loads(raw_body)
    event_type = event.get("event")

    if event_type == "order.paid":
        await _handle_order_paid(db, event)
    elif event_type == "payment.failed":
        await _handle_payment_failed(db, event)
    else:
        return {"received": True, "handled": False}

    await db.commit()
    return {"received": True, "handled": True}


async def _get_payment_for_order(db: AsyncSession, order_id: str) -> Payment | None:
    result = await db.execute(select(Payment).where(Payment.razorpay_order_id == order_id).with_for_update())
    return result.scalar_one_or_none()


async def _handle_order_paid(db: AsyncSession, event: dict) -> None:
    payload = event["payload"]
    order_entity = payload["order"]["entity"]
    payment_entity = payload["payment"]["entity"]

    payment = await _get_payment_for_order(db, order_entity["id"])
    if payment is None:
        raise HTTPException(status_code=404, detail="No matching payment record for this order")

    # Idempotency: webhooks can be delivered more than once, AND this can
    # race with /verify finalizing the same payment first — either order
    # of arrival is safe because of this guard.
    if payment.status == PaymentStatus.SUCCESS:
        return

    payment.razorpay_payment_id = payment_entity["id"]
    payment.status = PaymentStatus.SUCCESS

    # Apply the plan change that was priced at checkout time. Locks the
    # company row so this can't race with itself if /verify also fires.
    result = await db.execute(select(Company).where(Company.id == payment.company_id).with_for_update())
    company = result.scalar_one_or_none()
    if company is not None:
        company.pack = payment.plan_package
        company.tier = payment.plan_tier

    # NOTE: promo redemption is intentionally NOT handled here. It's
    # locked + incremented synchronously at checkout time (see
    # app/routers/payments.py::_lock_and_apply_promo), atomically with the
    # payment row's creation. A webhook-time-only lock can't prevent
    # over-redemption — by the time two webhooks arrive, Razorpay has
    # already collected money at the discounted price for both orders.
    #
    # payment_entity does not carry a signature in the webhook payload;
    # razorpay_signature is populated via the /verify endpoint's client-side
    # callback when available, and is not required for the ledger to be
    # authoritative — the webhook signature already authenticates this event.


async def _handle_payment_failed(db: AsyncSession, event: dict) -> None:
    payload = event["payload"]
    payment_entity = payload["payment"]["entity"]
    order_id = payment_entity.get("order_id")
    if not order_id:
        return

    payment = await _get_payment_for_order(db, order_id)
    if payment is None or payment.status != PaymentStatus.PENDING:
        return

    payment.status = PaymentStatus.FAILED

    if payment.applied_promo_id:
        # Free up the redemption slot locked at checkout time, since the
        # payment never actually completed.
        result = await db.execute(
            select(PromoCode).where(PromoCode.id == payment.applied_promo_id).with_for_update()
        )
        promo = result.scalar_one_or_none()
        if promo is not None and promo.current_uses > 0:
            promo.current_uses -= 1
