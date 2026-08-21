from asyncio.windows_events import NULL
import asyncio
import hmac
import hashlib
import json
import httpx
import os 
from dotenv import load_dotenv


load_dotenv()

BASE_URL = "http://localhost:8000"
WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
USER_JWT = "eyJhbGciOiJSUzI1NiIsImNhdCI6ImNsX0I3ZDRQRDIyMkFBQSIsImtpZCI6Imluc18zSHpHVjhYa1BKMTdVblJyMmJTbFFkejN1SjAiLCJ0eXAiOiJKV1QifQ.eyJleHAiOjE3ODc0MTgwNjcsImlhdCI6MTc4NzMzMTY2NywiaXNzIjoiaHR0cHM6Ly9mbGV4aWJsZS1zd2luZS01NDExLmNsZXJrLmFjY291bnRzLmRldiIsImp0aSI6IjYxODBkNDk0ODEyOGE4ODVlNjgyIiwibmJmIjoxNzg3MzMxNjYyLCJzdWIiOiJ1c2VyXzNJQklzQ3dDQk9IaENqWGJVelFEVVpOUHZWcSJ9.RNkTKSOs_9NJxLTlPgoVLjP8eplkeDx0M5kShdBCPw13v6VLQUF4RUx8g5Dr-JZ68zmtQ7gG8Zk_m_fHWoViqtvod2sIGh6aRi3FzrjKfrHkGkGNXkUA5JtASMHoeesMmWFQXQi6snRJtgS9-_aPHOzGMP2GA2AljWJyEMjVTwQ1E4VE8Io9b05ZKSzk2oPB7GzEDO7NMy1Xp2xRLllJoissOcuNi0B74JqGMtGnkecP0C7uHYtzGUO7Wmj3_3GT_yub1jtkUqXRovuKhNclytoxYSXjD-6yu66KL-yK5ZsD8o-HDYpUQ6o2E1C366GaLT9HB-7Tf6sCH8WOUENVqw"
COMPANY_ID = "638ef71a-6db4-4a0e-b150-67980ae8cdae"

ORDER_ID = "order_TSUo9WSycasIuQ"
PAYMENT_ID = "pay_TSUr6v4g5mWiNa"
msg = f"{ORDER_ID}|{PAYMENT_ID}"
SIGNATURE = hmac.new(
    RAZORPAY_KEY_SECRET.encode('utf-8'), 
    msg.encode('utf-8'), 
    hashlib.sha256
).hexdigest()

async def call_verify_endpoint(client: httpx.AsyncClient):
    payload = {
        "razorpay_order_id": ORDER_ID,
        "razorpay_payment_id": PAYMENT_ID,
        "razorpay_signature": SIGNATURE
    }
    headers = {"Authorization": f"Bearer {USER_JWT}"}
    try:
        response = await client.post(f"{BASE_URL}/companies/{COMPANY_ID}/payments/verify", json=payload, headers=headers)
        print(f"[VERIFY] Status: {response.status_code} | Body: {response.text}")
        return response
    except Exception as e:
        import traceback
        print(f"[VERIFY] Exception Type: {type(e).__name__}")
        print(f"[VERIFY] Exception Details: {repr(e)}")
        traceback.print_exc()

async def call_webhook_endpoint(client: httpx.AsyncClient):
    payload = {
        "event": "order.paid",
        "payload": {
            "order": {
                "entity": {
                    "id": ORDER_ID
                }
            },
            "payment": {
                "entity": {
                    "id": PAYMENT_ID,
                    "order_id": ORDER_ID,
                    "status": "captured"
                }
            }
        }
    }
    body_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    sig = hmac.new(WEBHOOK_SECRET.encode('utf-8'), body_bytes, hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-Razorpay-Signature": sig
    }
    try:
        response = await client.post(f"{BASE_URL}/webhooks/razorpay", content=body_bytes, headers=headers)
        print(f"[WEBHOOK] Status: {response.status_code} | Body: {response.text}")
        return response
    except Exception as e:
        print(f"[WEBHOOK] Exception: {e}")

async def main():
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Fire both requests simultaneously
        await asyncio.gather(
            call_verify_endpoint(client),
            call_webhook_endpoint(client)
        )

if __name__ == "__main__":
    asyncio.run(main())
