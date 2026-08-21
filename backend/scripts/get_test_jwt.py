"""
Mints a REAL Clerk session JWT for a given user, using Clerk's Backend API
directly — no frontend, no Account Portal, no hosted UI involved.

This is the officially documented testing flow: create a session for a
user, then create a session token from that session.
See: https://clerk.com/docs/guides/development/testing/overview

IMPORTANT: Clerk session tokens are short-lived — valid for only ~60
seconds. This script mints one and immediately prints it (and optionally
uses it right away against your local backend), but if you're testing
manually via curl/Postman, run this again to get a fresh token whenever
the old one expires.

Usage:
    python scripts/get_test_jwt.py <clerk_user_id>
    python scripts/get_test_jwt.py <clerk_user_id> --test-url http://localhost:8000/companies/me

Requires CLERK_SECRET_KEY as an environment variable (find it in Clerk
Dashboard -> API Keys -> Secret key. Starts with sk_test_...). This is
NOT the same as anything already in your backend .env — the running app
never needs this key, only this one-off testing script does.
"""

import argparse
import os
import sys

import requests

CLERK_API_BASE = "https://api.clerk.com/v1"


def mint_session_token(secret_key: str, user_id: str) -> str:
    headers = {"Authorization": f"Bearer {secret_key}", "Content-Type": "application/json"}

    # 1. Create a session for this user
    resp = requests.post(f"{CLERK_API_BASE}/sessions", headers=headers, json={"user_id": user_id})
    if not resp.ok:
        print(f"FAIL: could not create session — {resp.status_code} {resp.text}")
        sys.exit(1)
    session_id = resp.json()["id"]
    print(f"PASS: created session {session_id}")

    # 2. Create a token from that session
    # resp = requests.post(f"{CLERK_API_BASE}/sessions/{session_id}/tokens", headers=headers, json={})
    resp = requests.post(f"{CLERK_API_BASE}/sessions/{session_id}/tokens/dev_token", headers=headers, json={})
    if not resp.ok:
        print(f"FAIL: could not create session token — {resp.status_code} {resp.text}")
        sys.exit(1)
    jwt = resp.json()["jwt"]
    print("PASS: minted session token (valid ~60 seconds)")
    return jwt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("user_id", help="Clerk user id, e.g. user_2abc... (copy from Clerk Dashboard -> Users)")
    parser.add_argument("--test-url", help="If set, immediately calls this URL with the token and prints the response")
    args = parser.parse_args()

    secret_key = os.environ.get("CLERK_SECRET_KEY")
    if not secret_key:
        print("FAIL: set CLERK_SECRET_KEY as an environment variable first (Clerk Dashboard -> API Keys -> Secret key)")
        sys.exit(1)

    jwt = mint_session_token(secret_key, args.user_id)
    print(f"\nJWT:\n{jwt}\n")

    if args.test_url:
        resp = requests.get(args.test_url, headers={"Authorization": f"Bearer {jwt}"})
        print(f"Called {args.test_url} -> {resp.status_code}")
        print(resp.text)
    else:
        print("Use it immediately (within ~60s) like:")
        print(f'  curl http://localhost:8000/companies/me -H "Authorization: Bearer {jwt}"')


if __name__ == "__main__":
    main()
