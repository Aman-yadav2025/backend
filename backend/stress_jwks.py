import asyncio
import time
import jwt
from unittest.mock import AsyncMock, patch
import httpx

from app.security import SafeJWKSClient
async def fake_get(*args, **kwargs):
    await asyncio.sleep(0.1) # Simulate 100ms network latency
    class FakeResponse:
        def raise_for_status(self): pass
        def json(self): return {"keys": []}
    return FakeResponse()

async def stress_test():
    client = SafeJWKSClient(jwks_url="http://fake-clerk.com/.well-known/jwks.json", ttl=1)
    
    # Create a fake token with kid="fake_kid"
    token = jwt.encode({"sub": "user123"}, "secret", algorithm="HS256", headers={"kid": "fake_kid"})

    failures = 0
    
    async def worker():
        nonlocal failures
        try:
            await client.get_signing_key_from_jwt(token)
        except jwt.PyJWTError:
            failures += 1
        except Exception as e:
            print(f"Unexpected error: {e}")

    print("Starting JWKS stress test with 10,000 concurrent requests...")
    start_time = time.monotonic()
    
    # Patch httpx.AsyncClient.get globally for all tasks
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=fake_get) as mock_get:
        tasks = [worker() for _ in range(10000)]
        await asyncio.gather(*tasks)
        
        print(f"Actual network calls made to Clerk: {mock_get.call_count}")

    end_time = time.monotonic()
    
    print(f"Stress test completed in {end_time - start_time:.2f} seconds.")
    print(f"Expected Failures (401 Unauthorized due to invalid kid): {failures} / 10000")
    print(f"Double-Checked Lock Throttling: If network calls == 1, throttling was PERFECT.")
    
if __name__ == "__main__":
    asyncio.run(stress_test())
