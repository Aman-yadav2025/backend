"""
Simulates a real Razorpay webhook delivery — builds an order.paid payload
using a REAL order_id/payment_id you already have (e.g. from a payments
row that's already SUCCESS), signs it correctly with your webhook secret,
and POSTs it to your local backend directly.

This is for testing idempotency (does resending order.paid double-process
a payment?) when Razorpay's dashboard doesn't offer a resend/replay button
for past webhook deliveries.

Usage:
    python scripts/simulate_razorpay_webhook.py order_ABC123 pay_XYZ789

Requires RAZORPAY_WEBHOOK_SECRET as an environment variable (same value
as in your .env — copy it in for this one-off run).
"""

import argparse
import hashlib
import hmac
import json
import os
import sys

import requests


def build_payload(order_id: str, payment_id: str) -> dict:
    return {
        "entity": "event",
        "event": "order.paid",
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "order_id": order_id,
                    "status": "captured",
                    "amount": 449900,
                    "currency": "INR",
                }
            },
            "order": {
                "entity": {
                    "id": order_id,
                    "status": "paid",
                    "amount": 449900,
                    "currency": "INR",
                }
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("order_id", help="A real razorpay_order_id from an existing payments row")
    parser.add_argument("payment_id", help="The matching razorpay_payment_id from that same row")
    parser.add_argument("--url", default="http://localhost:8000/webhooks/razorpay")
    args = parser.parse_args()

    secret = os.environ.get("RAZORPAY_WEBHOOK_SECRET")
    if not secret:
        print("FAIL: set RAZORPAY_WEBHOOK_SECRET as an environment variable first")
        sys.exit(1)

    payload = build_payload(args.order_id, args.payment_id)
    # Must sign the EXACT bytes we send — sign first, reuse the same bytes.
    raw_body = json.dumps(payload).encode()
    signature = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()

    resp = requests.post(
        args.url,
        data=raw_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": signature},
    )
    print(f"POST {args.url} -> {resp.status_code}")
    print(resp.text)


if __name__ == "__main__":
    main()
