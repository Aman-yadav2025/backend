import asyncio
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

class MockEvent:
    def __init__(self, order_id, payment_id):
        self.event_type = "order.paid"
        self.order_id = order_id
        self.payment_id = payment_id

async def test_razorpay_webhooks():
    print("Running tests for razorpay_webhooks.py updates...\n")
    
    mock_db = AsyncMock()
    
    event_payload = {
        "event": "order.paid",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test123",
                    "order_id": "order_test123"
                }
            }
        }
    }
    
    # 1. Test successful refund
    print("Test 1: Successful Razorpay Refund on CANCELLED order")
    mock_purchase = MockPurchase(PurchaseStatus.CANCELLED)
    
    # Mock db.scalar to return our MockPurchase when _get_deal_purchase_for_order is called
    mock_db.scalar.return_value = mock_purchase
    
    with patch("app.routers.razorpay_webhooks.razorpay_client") as mock_client:
        mock_client.refund_payment = AsyncMock()
        mock_client.verify_webhook_signature.return_value = True
        
        request = MagicMock()
        request.body = AsyncMock(return_value=b"test_body")
        
        res = await handle_razorpay_webhook(
            request=request,
            x_razorpay_signature="test_sig",
            db=mock_db
        )
        
        assert res == {"received": True, "handled": True}
        assert mock_purchase.razorpay_payment_id == "pay_test123"
        mock_client.refund_payment.assert_called_once()
        print("✅ Test 1 passed\n")

    # 2. Test idempotency loop fix ("already refunded")
    print("Test 2: Idempotency recovery when Razorpay throws 'refund' error")
    mock_purchase = MockPurchase(PurchaseStatus.CANCELLED)
    mock_db.scalar.return_value = mock_purchase
    
    with patch("app.routers.razorpay_webhooks.razorpay_client") as mock_client:
        mock_client.refund_payment = AsyncMock(side_effect=Exception("Payment has been fully refunded already"))
        mock_client.verify_webhook_signature.return_value = True
        
        request = MagicMock()
        request.body = AsyncMock(return_value=b"test_body")
        
        res = await handle_razorpay_webhook(
            request=request,
            x_razorpay_signature="test_sig",
            db=mock_db
        )
        
        # It should swallow the error, mark as handled, and return successfully
        assert res == {"received": True, "handled": True}
        assert mock_purchase.razorpay_payment_id == "pay_test123"
        print("✅ Test 2 passed\n")

    # 3. Test generic 502 failure on refund
    print("Test 3: Abort transaction (502) if refund fails due to generic error")
    mock_purchase = MockPurchase(PurchaseStatus.CANCELLED)
    mock_db.scalar.return_value = mock_purchase
    
    with patch("app.routers.razorpay_webhooks.razorpay_client") as mock_client:
        mock_client.refund_payment = AsyncMock(side_effect=Exception("Internal server error from Razorpay"))
        mock_client.verify_webhook_signature.return_value = True
        
        request = MagicMock()
        request.body = AsyncMock(return_value=b"test_body")
        
        try:
            await handle_razorpay_webhook(
                request=request,
                x_razorpay_signature="test_sig",
                db=mock_db
            )
            print("❌ Test 3 failed: Expected HTTPException(502) but got success")
        except HTTPException as e:
            assert e.status_code == 502
            assert mock_purchase.razorpay_payment_id is None # State should NOT be updated
            print("✅ Test 3 passed\n")

    print("🎉 All tests passed successfully!")

if __name__ == "__main__":
    asyncio.run(test_razorpay_webhooks())
