import json
import hmac
import hashlib
import argparse
import requests

API_BASE_URL = "http://localhost:8000"
WEBHOOK_SECRET = "Plastic_ai_ek_chutiya_app_backend_testing"

def generate_signature(payload_str: str, secret: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        payload_str.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

def test_direct_payment_flow(token: str, company_id: str, listing_id: str):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    print("1. Creating a DIRECT purchase...")
    purchase_data = {
        "quantity": "100.00",
        "payment_method": "DIRECT"
    }
    
    resp = requests.post(f"{API_BASE_URL}/companies/{company_id}/marketplace/{listing_id}/purchase", headers=headers, json=purchase_data)
    if resp.status_code not in (200, 201):
        print(f"Failed to create purchase: {resp.status_code}")
        print(resp.json())
        return
        
    purchase = resp.json()
    purchase_id = purchase["id"]
    order_id = purchase["razorpay_order_id"]
    print(f"✅ Purchase created successfully! ID: {purchase_id}, Order ID: {order_id}")
    print(f"Status: {purchase['purchase_status']}, Payment Method: {purchase['payment_method']}")

    print("\n2. Simulating Razorpay payment.failed webhook...")
    failed_payload = {
        "event": "payment.failed",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_failed_123",
                    "order_id": order_id,
                    "status": "failed"
                }
            }
        }
    }
    failed_payload_str = json.dumps(failed_payload, separators=(',', ':'))
    failed_sig = generate_signature(failed_payload_str, WEBHOOK_SECRET)
    
    wh_resp = requests.post(
        f"{API_BASE_URL}/webhooks/razorpay",
        headers={"x-razorpay-signature": failed_sig, "Content-Type": "application/json"},
        data=failed_payload_str
    )
    print(f"Webhook (failed) response: {wh_resp.status_code} - {wh_resp.json()}")

    print("\n3. Verifying purchase was NOT cancelled (should still be AWAITING_PAYMENT)...")
    get_resp = requests.get(f"{API_BASE_URL}/companies/{company_id}/marketplace/purchases", headers=headers)
    purchases = get_resp.json()
    purchase_still_open = any(p["id"] == purchase_id for p in purchases)
    if purchase_still_open:
        print("✅ Purchase is still open (AWAITING_PAYMENT) after payment failure!")
    else:
        print("❌ Error: Purchase was closed/cancelled after payment failure!")

    print("\n4. Simulating Razorpay order.paid webhook...")
    paid_payload = {
        "event": "order.paid",
        "payload": {
            "order": {
                "entity": {
                    "id": order_id,
                    "status": "paid",
                    "notes": {
                        "purpose": "deal_purchase"
                    }
                }
            },
            "payment": {
                "entity": {
                    "id": "pay_success_123",
                    "order_id": order_id,
                    "status": "captured"
                }
            }
        }
    }
    paid_payload_str = json.dumps(paid_payload, separators=(',', ':'))
    paid_sig = generate_signature(paid_payload_str, WEBHOOK_SECRET)

    wh_resp_paid = requests.post(
        f"{API_BASE_URL}/webhooks/razorpay",
        headers={"x-razorpay-signature": paid_sig, "Content-Type": "application/json"},
        data=paid_payload_str
    )
    print(f"Webhook (paid) response: {wh_resp_paid.status_code} - {wh_resp_paid.json()}")

    print("\n5. Verifying purchase was confirmed...")
    get_resp_confirmed = requests.get(f"{API_BASE_URL}/companies/{company_id}/marketplace/purchases", headers=headers)
    confirmed_purchases = get_resp_confirmed.json()
    purchase_confirmed = any(p["id"] == purchase_id for p in confirmed_purchases)
    
    if purchase_confirmed:
        print("✅ Purchase successfully confirmed!")
    else:
        print("❌ Error: Purchase was not found in CONFIRMED status.")
        
    print("\n6. Verifying cancel API on a confirmed direct payment...")
    cancel_resp = requests.post(f"{API_BASE_URL}/companies/{company_id}/marketplace/purchases/{purchase_id}/cancel", headers=headers)
    print(f"Cancel Response: {cancel_resp.status_code}")
    if cancel_resp.status_code == 400:
        print("✅ Cancel rejected correctly for a CONFIRMED purchase.")
    else:
        print("❌ Unexpected behavior for cancel!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Direct Payment flow")
    parser.add_argument("--token", required=True, help="Brand auth token")
    parser.add_argument("--company-id", required=True, help="Brand company UUID")
    parser.add_argument("--listing-id", required=True, help="Material Listing ID to purchase")
    args = parser.parse_args()
    
    test_direct_payment_flow(args.token, args.company_id, args.listing_id)
