"""
Simulates a real Razorpay webhook delivery — builds a webhook payload
using a REAL order_id/payment_id you already have (e.g. from a payments
row), signs it correctly with your webhook secret, and POSTs it to your 
local backend directly.

This is for testing idempotency, success paths, and failure paths when 
Razorpay's dashboard doesn't offer a resend/replay button for past deliveries.

Usage:
    python scripts/simulate_razorpay_webhook.py order_ABC123 pay_XYZ789
    python scripts/simulate_razorpay_webhook.py order_ABC123 pay_XYZ789 --event payment.failed --amount 5000

Requires RAZORPAY_WEBHOOK_SECRET in your .env file or environment.
"""

import argparse
import hashlib
import hmac
import json
import os
import sys

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()  # Auto-load the .env file if available
except ImportError:
    pass


def build_payload(event: str, order_id: str, payment_id: str, amount_paise: int) -> dict:
    payment_status = "captured" if event == "order.paid" else "failed"
    order_status = "paid" if event == "order.paid" else "attempted"
    
    return {
        "entity": "event",
        "event": event,
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "order_id": order_id,
                    "status": payment_status,
                    "amount": amount_paise,
                    "currency": "INR",
                }
            },
            "order": {
                "entity": {
                    "id": order_id,
                    "status": order_status,
                    "amount": amount_paise,
                    "currency": "INR",
                }
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate Razorpay Webhooks locally.")
    parser.add_argument("order_id", help="A real razorpay_order_id from an existing payments row")
    parser.add_argument("payment_id", help="The matching razorpay_payment_id from that same row")
    parser.add_argument("--event", default="order.paid", choices=["order.paid", "payment.failed"], help="The webhook event to simulate")
    parser.add_argument("--amount", type=float, default=4499.0, help="Amount in INR (default: 4499.0)")
    parser.add_argument("--url", default="http://localhost:8000/webhooks/razorpay", help="Local backend webhook URL")
    args = parser.parse_args()

    secret = os.environ.get("RAZORPAY_WEBHOOK_SECRET")
    if not secret:
        print("FAIL: set RAZORPAY_WEBHOOK_SECRET in your .env file or environment first")
        sys.exit(1)

    amount_paise = int(args.amount * 100)
    payload = build_payload(args.event, args.order_id, args.payment_id, amount_paise)
    
    # Must sign the EXACT bytes we send — sign first, reuse the same bytes.
    raw_body = json.dumps(payload).encode()
    signature = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()

    resp = requests.post(
        args.url,
        data=raw_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": signature},
    )
    print(f"POST {args.url} (Event: {args.event}, Amount: {args.amount}) -> HTTP {resp.status_code}")
    print(resp.text)


if __name__ == "__main__":
    main()
