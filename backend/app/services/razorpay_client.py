import asyncio
import hashlib
import hmac

import razorpay

from app.config import settings

_client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret.get_secret_value()))


async def create_order(amount_in_rupees: float, currency: str, receipt: str, notes: dict) -> dict:
    amount_in_paise = int(round(amount_in_rupees * 100))
    def _create():
        return _client.order.create(
            {
                "amount": amount_in_paise,
                "currency": currency,
                "receipt": receipt,
                "notes": notes,
                "payment_capture": 1,
            }
        )
    return await asyncio.to_thread(_create)


def verify_payment_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """Client-side confirmation callback check (fast UX path). The webhook
    handler is still the source of truth for finalizing payment status.
    """
    try:
        _client.utility.verify_payment_signature(
            {
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature,
            }
        )
        return True
    except razorpay.errors.SignatureVerificationError:
        return False


def verify_webhook_signature(payload_body: bytes, received_signature: str) -> bool:
    expected = hmac.new(
        settings.razorpay_webhook_secret.get_secret_value().encode(),
        payload_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, received_signature)


async def refund_payment(payment_id: str, amount_in_rupees: float, receipt: str) -> dict:
    """Initiates a refund via Razorpay API."""
    # if payment_id.startswith("pay_dummy"):
    #     import uuid
    #     return {"id": f"rfnd_dummy_{uuid.uuid4().hex[:6]}"}
        
    amount_in_paise = int(round(amount_in_rupees * 100))
    def _refund():
        return _client.payment.refund(
            payment_id,
            {
                "amount": amount_in_paise,
                "receipt": receipt,
            }
        )
    return await asyncio.to_thread(_refund)
