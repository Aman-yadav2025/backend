import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Company, Payment, PaymentStatus, PromoCode, WalletRecharge, WalletRechargeStatus, MaterialPurchase, PurchaseStatus, MaterialListing
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


async def _get_recharge_for_order(db: AsyncSession, order_id: str) -> WalletRecharge | None:
    result = await db.execute(
        select(WalletRecharge).where(WalletRecharge.razorpay_order_id == order_id).with_for_update()
    )
    return result.scalar_one_or_none()


async def _get_deal_purchase_for_order(db: AsyncSession, order_id: str) -> MaterialPurchase | None:
    result = await db.execute(
        select(MaterialPurchase).where(MaterialPurchase.razorpay_order_id == order_id).with_for_update()
    )
    return result.scalar_one_or_none()


async def _handle_order_paid(db: AsyncSession, event: dict) -> None:
    payload = event["payload"]
    order_entity = payload["order"]["entity"]
    payment_entity = payload["payment"]["entity"]
    order_id = order_entity["id"]

    # Determine order purpose from Razorpay notes set at checkout time.
    notes = order_entity.get("notes", {})
    purpose = notes.get("purpose", "")

    if purpose == "wallet_recharge":
        # ── Wallet recharge order ─────────────────────────────────────────
        recharge = await _get_recharge_for_order(db, order_id)
        if recharge is None:
            raise HTTPException(status_code=404, detail="No matching wallet recharge record for this order")

        # Idempotency guard
        if recharge.status == WalletRechargeStatus.SUCCESS.value:
            return

        recharge.razorpay_payment_id = payment_entity["id"]
        recharge.status = WalletRechargeStatus.SUCCESS.value

        # Credit the company wallet atomically
        company_result = await db.execute(
            select(Company).where(Company.id == recharge.company_id).with_for_update()
        )
        company = company_result.scalar_one_or_none()
        if company is not None:
            company.wallet_balance += recharge.amount

    elif purpose == "deal_purchase":
        # ── Direct deal purchase order ───────────────────────────────────
        purchase = await _get_deal_purchase_for_order(db, order_id)
        if purchase is None:
            # Orphaned order: the Razorpay order was created but the purchase
            # row was never saved (e.g., stock ran out after order creation).
            # Return 200 so Razorpay stops retrying — there is nothing to do.
            return

        if purchase.purchase_status == PurchaseStatus.CONFIRMED:
            return

        if purchase.purchase_status == PurchaseStatus.CANCELLED:
            # The brand cancelled the order before the payment completed, but
            # the payment succeeded anyway. Refund the money via Razorpay.
            if purchase.razorpay_payment_id:
                return
            try:
                await razorpay_client.refund_payment(
                    payment_id=payment_entity["id"],
                    amount_in_rupees=float(purchase.total_price),
                    receipt=f"rfnd_cxl_{str(purchase.id)[:20]}"
                )
                # Only mark as handled once the refund succeeds
                purchase.razorpay_payment_id = payment_entity["id"]
            except Exception as e:
                error_msg = str(e).lower()
                if "refund" in error_msg:
                    # The payment was already refunded (e.g., from a previous webhook 
                    # attempt where the DB commit failed). Mark as handled.
                    logging.warning(f"Refund already processed for {purchase.id}: {e}")
                    purchase.razorpay_payment_id = payment_entity["id"]
                    return

                logging.error(f"Failed to refund cancelled purchase {purchase.id}: {e}")
                # Raise 502 so the DB transaction aborts and Razorpay retries the webhook
                raise HTTPException(status_code=502, detail="Failed to refund payment via Razorpay")
            return

        purchase.razorpay_payment_id = payment_entity["id"]
        purchase.purchase_status = PurchaseStatus.CONFIRMED

        # Credit the recycler's wallet now that payment is secured
        listing = await db.execute(select(MaterialListing).where(MaterialListing.id == purchase.listing_id))
        listing = listing.scalar_one_or_none()
        if listing and listing.recycler_id:
            recycler_company = await db.execute(
                select(Company).where(Company.id == listing.recycler_id).with_for_update()
            )
            recycler_company = recycler_company.scalar_one_or_none()
            if recycler_company:
                recycler_company.wallet_balance += purchase.total_price
                recycler_company.frozen_wallet_balance += purchase.total_price

    else:
        # ── Subscription / plan payment order ────────────────────────────
        payment = await _get_payment_for_order(db, order_id)
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

    # Check if this is a wallet recharge failure
    recharge = await _get_recharge_for_order(db, order_id)
    if recharge is not None:
        if recharge.status == WalletRechargeStatus.PENDING.value:
            recharge.status = WalletRechargeStatus.FAILED.value
        return

    # Check if this is a direct deal purchase failure.
    # IMPORTANT: do NOT cancel the purchase here. Razorpay fires payment.failed
    # for each individual payment attempt, but the order remains open for retry
    # until it expires (15 minutes). If we cancel + restore inventory here and
    # the brand retries successfully, order.paid fires — but by then the purchase
    # is CANCELLED so we silently ignore it, leaving the brand's money collected
    # with no purchase record. Instead, let the brand cancel explicitly via the
    # cancel API, or the order expires naturally with no further action needed.
    #
    # Use a plain (non-locking) read since we make no writes — holding a
    # FOR UPDATE lock while doing nothing would block concurrent order.paid
    # webhooks for the same purchase from acquiring their own lock.
    deal_exists = await db.scalar(
        select(MaterialPurchase.id).where(MaterialPurchase.razorpay_order_id == order_id)
    )
    if deal_exists is not None:
        # Nothing to do on a single failed attempt — just acknowledge.
        return

    # Otherwise treat as a plan payment failure
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
