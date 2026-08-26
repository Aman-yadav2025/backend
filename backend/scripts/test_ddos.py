import asyncio
import time
import httpx
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
PORT = os.getenv("PORT", "8000")

# The URL to attack. The /health endpoint uses the global default limit of 100/minute.
TARGET_URL = f"http://localhost:{PORT}/health"
TOTAL_REQUESTS = 150  # We send 150 requests. The limit is 100, so we expect ~50 rejections.

async def fetch(client: httpx.AsyncClient, i: int):
    try:
        # We spoof a random CF-Connecting-IP so Cloudflare bypass doesn't trigger, 
        # but we use the SAME IP for all requests to trigger the rate limiter.
        headers = {"CF-Connecting-IP": "203.0.113.50"}
        response = await client.get(TARGET_URL, headers=headers)
        return response.status_code
    except Exception as e:
        return str(e)

async def main():
    print(f"🔥 Launching DDoS Simulation against {TARGET_URL} 🔥")
    print(f"Sending {TOTAL_REQUESTS} requests simultaneously...\n")
    
    start_time = time.time()
    
    async with httpx.AsyncClient() as client:
        # Fire all requests concurrently
        tasks = [fetch(client, i) for i in range(TOTAL_REQUESTS)]
        results = await asyncio.gather(*tasks)
    
    elapsed = time.time() - start_time
    
    # Tally the results
    successes = results.count(200)
    rate_limited = results.count(429)
    errors = len(results) - successes - rate_limited
    
    print("=== Attack Results ===")
    print(f"Total Time Taken : {elapsed:.2f} seconds")
    print(f"✅ Success (200)  : {successes} requests")
    print(f"🛑 Blocked (429)  : {rate_limited} requests")
    if errors > 0:
        print(f"⚠️ Other Errors   : {errors} requests")
        
    print("\n=== Analysis ===")
    if successes <= 100 and rate_limited > 0:
        print("🛡️ SUCCESS: The Rate Limiter successfully defended the server!")
    else:
        print("❌ FAIL: The Rate Limiter leaked or did not block the attack.")

if __name__ == "__main__":
    asyncio.run(main())
