"""
Razorpay Webhooks – Unit Tests
================================
Tests the handle_razorpay_webhook handler with mocked DB and Razorpay client.
Run with: python -m pytest test_razorpay_webhooks.py -v
"""
import pytest
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from app.routers.razorpay_webhooks import handle_razorpay_webhook
from app.models import PurchaseStatus, MaterialPurchase, MaterialListing, Company
from app.schemas import PaymentMethod


class MockPurchase:
    def __init__(self, status):
        self.id = uuid.uuid4()
        self.brand_id = uuid.uuid4()
        self.listing_id = uuid.uuid4()
        self.purchase_status = status
        self.total_price = Decimal("100.50")
        self.razorpay_payment_id = None
        self.payment_method = PaymentMethod.DIRECT


import json


_VALID_PAYLOAD = {
    "event": "order.paid",
    "payload": {
        "order": {
            "entity": {
                "id": "order_test123",
                "notes": {"purpose": "deal_purchase"},
            }
        },
        "payment": {
            "entity": {
                "id": "pay_test123",
                "order_id": "order_test123",
            }
        },
    },
}


def _make_request():
    request = MagicMock()
    request.body = AsyncMock(return_value=json.dumps(_VALID_PAYLOAD).encode())
    return request


def _make_db_mock(purchase):
    """Returns a mock db where _get_deal_purchase_for_order returns purchase."""
    mock_db = AsyncMock()
    purchase_result = MagicMock()
    purchase_result.scalar_one_or_none.return_value = purchase
    mock_db.execute.return_value = purchase_result
    return mock_db


@pytest.mark.anyio
async def test_successful_refund_on_cancelled_order():
    """
    When a CANCELLED order receives an order.paid webhook, it should be
    refunded via Razorpay and the handler should return handled=True.
    """
    mock_purchase = MockPurchase(PurchaseStatus.CANCELLED)
    mock_db = _make_db_mock(mock_purchase)

    with patch("app.routers.razorpay_webhooks.razorpay_client") as mock_client:
        mock_client.refund_payment = AsyncMock()
        mock_client.verify_webhook_signature.return_value = True

        res = await handle_razorpay_webhook(
            request=_make_request(),
            x_razorpay_signature="test_sig",
            db=mock_db,
        )

    assert res == {"received": True, "handled": True}
    mock_client.refund_payment.assert_called_once()


@pytest.mark.anyio
async def test_idempotency_already_refunded():
    """
    When Razorpay returns 'already refunded', the handler should swallow the
    error and still return handled=True (idempotency recovery).
    """
    mock_purchase = MockPurchase(PurchaseStatus.CANCELLED)
    mock_db = _make_db_mock(mock_purchase)

    with patch("app.routers.razorpay_webhooks.razorpay_client") as mock_client:
        mock_client.refund_payment = AsyncMock(
            side_effect=Exception("Payment has been fully refunded already")
        )
        mock_client.verify_webhook_signature.return_value = True

        res = await handle_razorpay_webhook(
            request=_make_request(),
            x_razorpay_signature="test_sig",
            db=mock_db,
        )

    assert res == {"received": True, "handled": True}


@pytest.mark.anyio
async def test_generic_refund_error_raises_502():
    """
    When a generic (non-idempotent) refund error occurs, the handler should
    raise HTTPException(502) and NOT update the purchase state.
    """
    mock_purchase = MockPurchase(PurchaseStatus.CANCELLED)
    mock_db = _make_db_mock(mock_purchase)

    with patch("app.routers.razorpay_webhooks.razorpay_client") as mock_client:
        mock_client.refund_payment = AsyncMock(
            side_effect=Exception("Internal server error from Razorpay")
        )
        mock_client.verify_webhook_signature.return_value = True

        with pytest.raises(HTTPException) as exc_info:
            await handle_razorpay_webhook(
                request=_make_request(),
                x_razorpay_signature="test_sig",
                db=mock_db,
            )

    assert exc_info.value.status_code == 502
