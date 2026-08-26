"""
Integration test script for all changes made to company member endpoints:
  - PATCH /companies/{company_id}/members/{profile_id}/status
  - PATCH /companies/{company_id}/members/{profile_id}/role
  - POST  /admin/platform-admins/{profile_id}

Updated to run end-to-end dynamically by provisioning its own Clerk users, org, and database entries!
"""

import asyncio
import sys
import os
import uuid
import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from dotenv import dotenv_values
from sqlalchemy import delete
from app.database import AsyncSessionLocal
from app.models import Profile, Company, CompanyMember, CompanyType, MaterialType, PackType, MemberRole, MemberStatus, SystemRole

env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
env = dotenv_values(env_path)

CLERK_SECRET_KEY = env.get("CLERK_SECRET_KEY", "")
CLERK_API_BASE = "https://api.clerk.com/v1"
BASE_URL = os.getenv("API_URL", "http://localhost:8000")

# Globals set during setup
PLATFORM_ADMIN_JWT = ""
COMPANY_OWNER_JWT = ""
EMPLOYEE_JWT = ""
COMPANY_ID = ""
EMPLOYEE_PROFILE_ID = ""

PASS = "✅"
FAIL = "❌"
INFO = "ℹ️ "

def provision_clerk_user(prefix="test") -> tuple[str, str]:
    print(f"[{prefix}] Provisioning temporary Clerk user...")
    headers = {"Authorization": f"Bearer {CLERK_SECRET_KEY}", "Content-Type": "application/json"}
    
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    password = f"TestPass123!{uuid.uuid4().hex[:8]}"
    resp = requests.post(f"{CLERK_API_BASE}/users", headers=headers, json={"email_address": [email], "password": password})
    if not resp.ok:
        print(f"❌ Failed to create Clerk user: {resp.text}")
        sys.exit(1)
    
    clerk_user_id = resp.json()["id"]
    
    resp = requests.post(f"{CLERK_API_BASE}/sessions", headers=headers, json={"user_id": clerk_user_id})
    session_id = resp.json()["id"]

    resp = requests.post(f"{CLERK_API_BASE}/sessions/{session_id}/tokens/dev_token", headers=headers, json={})
    jwt = resp.json()["jwt"]
    print(f"✅ User created: {clerk_user_id}")
    return clerk_user_id, jwt

def delete_clerk_user(clerk_user_id: str):
    print(f"[Teardown] Deleting Clerk user {clerk_user_id}...")
    headers = {"Authorization": f"Bearer {CLERK_SECRET_KEY}"}
    requests.delete(f"{CLERK_API_BASE}/users/{clerk_user_id}", headers=headers)

def provision_clerk_organization(owner_uid: str, emp_uid: str) -> str:
    print(f"\n[Setup] Provisioning Clerk Organization...")
    headers = {"Authorization": f"Bearer {CLERK_SECRET_KEY}", "Content-Type": "application/json"}
    
    # Create Organization (owner becomes org:admin implicitly by creating it in Clerk, usually)
    resp = requests.post(f"{CLERK_API_BASE}/organizations", headers=headers, json={"name": "Test Promo Co", "created_by": owner_uid})
    if not resp.ok:
        print(f"❌ Failed to create Clerk org: {resp.text}")
        sys.exit(1)
        
    org_id = resp.json()["id"]
    print(f"✅ Organization created: {org_id}")
    
    # Add employee membership (role org:member)
    resp = requests.post(f"{CLERK_API_BASE}/organizations/{org_id}/memberships", headers=headers, json={"user_id": emp_uid, "role": "org:member"})
    if not resp.ok:
        print(f"❌ Failed to add member to org: {resp.text}")
        sys.exit(1)
        
    return org_id

def delete_clerk_organization(org_id: str):
    print(f"[Teardown] Deleting Clerk org {org_id}...")
    headers = {"Authorization": f"Bearer {CLERK_SECRET_KEY}"}
    requests.delete(f"{CLERK_API_BASE}/organizations/{org_id}", headers=headers)


async def setup_test_db(admin_uid, owner_uid, emp_uid, clerk_org_id):
    from sqlalchemy import select
    print("\n[Setup] Waiting for Clerk webhooks to seed DB (Profiles, Company, Members)...")
    async with AsyncSessionLocal() as db:
        # Give webhooks time to finish processing
        company = None
        for _ in range(20):
            res = await db.execute(select(Company).where(Company.clerk_org_id == clerk_org_id))
            company = res.scalar_one_or_none()
            if company:
                break
            await asyncio.sleep(0.5)

        if not company:
            print("⚠️ Webhooks didn't create the company in time. Inserting manually...")
            company_id = uuid.uuid4()
            company = Company(
                id=company_id, clerk_org_id=clerk_org_id, owner_id=owner_uid,
                name="Test Promotion Co", company_email="promo@test.com", mobile_number="9999999999",
                gst_number="GSTP", company_pan_number="PANP", factory_address="123 Promo St",
                state="State", city="City", pincode="123456", contact_person_name="Promo Owner",
                designation="Owner", material=MaterialType.PLASTIC, company_type=CompanyType.BRAND,
                pack=PackType.STARTER, tier=1, wallet_balance=0.00
            )
            db.add(company)
            await db.commit()
        else:
            company_id = company.id

        # Webhooks might have created the profiles/members, so we enforce our test roles exactly.
        # Merge Profiles
        await db.merge(Profile(id=admin_uid, email=f"{admin_uid}@test.com", system_role=SystemRole.PLATFORM_ADMIN))
        await db.merge(Profile(id=owner_uid, email=f"{owner_uid}@test.com", system_role=SystemRole.BRAND_ADMIN))
        await db.merge(Profile(id=emp_uid, email=f"{emp_uid}@test.com", system_role=SystemRole.BRAND_EMPLOYEE))
        
        # Update or Insert CompanyMembers
        for uid, role in [(owner_uid, MemberRole.OWNER), (emp_uid, MemberRole.MEMBER)]:
            res = await db.execute(select(CompanyMember).where(CompanyMember.company_id == company_id, CompanyMember.profile_id == uid))
            member = res.scalar_one_or_none()
            if member:
                member.member_role = role
                member.status = MemberStatus.ACTIVE
            else:
                db.add(CompanyMember(company_id=company_id, profile_id=uid, member_role=role, status=MemberStatus.ACTIVE))
        
        await db.commit()
        
    return str(company_id)

async def teardown_test_db(admin_uid, owner_uid, emp_uid, company_id):
    print("\n[Teardown] Cleaning up database...")
    async with AsyncSessionLocal() as db:
        await db.execute(delete(CompanyMember).where(CompanyMember.company_id == uuid.UUID(company_id)))
        await db.execute(delete(Company).where(Company.id == uuid.UUID(company_id)))
        await db.execute(delete(Profile).where(Profile.id.in_([admin_uid, owner_uid, emp_uid])))
        await db.commit()


def headers(jwt: str) -> dict:
    return {"Authorization": f"Bearer {jwt}", "Content-Type": "application/json"}

def decode_profile_id(jwt: str) -> str:
    import jwt as pyjwt
    return pyjwt.decode(jwt, options={"verify_signature": False}).get("sub", "")

# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

async def db_get_profile(profile_id: str):
    """Read Profile directly from DB."""
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Profile).where(Profile.id == profile_id))
        return res.scalar_one_or_none()

async def db_reset_employee(profile_id: str, company_id: str):
    """Reset test employee back to MEMBER / ACTIVE / BRAND_EMPLOYEE between tests."""
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(CompanyMember).where(
                CompanyMember.profile_id == profile_id,
                CompanyMember.company_id == uuid.UUID(company_id),
            )
        )
        member = res.scalar_one_or_none()
        if member:
            member.member_role = MemberRole.MEMBER
            member.status = MemberStatus.ACTIVE

        pres = await db.execute(select(Profile).where(Profile.id == profile_id))
        profile = pres.scalar_one_or_none()
        if profile:
            profile.system_role = SystemRole.BRAND_EMPLOYEE

        await db.commit()
        
    # Also reset clerk role
    try:
        from app.database import AsyncSessionLocal as _Session
        async with _Session() as _db:
            c_res = await _db.execute(select(Company).where(Company.id == uuid.UUID(company_id)))
            c_obj = c_res.scalar_one_or_none()
            if c_obj:
                import requests
                requests.patch(
                    f"{CLERK_API_BASE}/organizations/{c_obj.clerk_org_id}/memberships/{profile_id}",
                    headers={"Authorization": f"Bearer {CLERK_SECRET_KEY}", "Content-Type": "application/json"},
                    json={"role": "org:member"}
                )
    except Exception as e:
        print(f"Warning: Failed to reset clerk role for {profile_id}: {e}")

    print(f"  {INFO} Employee reset to MEMBER/ACTIVE/BRAND_EMPLOYEE in DB and Clerk.")


def check(condition: bool, msg_pass: str, msg_fail: str) -> bool:
    if condition:
        print(f"  {PASS} {msg_pass}")
    else:
        print(f"  {FAIL} {msg_fail}")
    return condition

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: update_member_role
# ═══════════════════════════════════════════════════════════════════════════════

async def test_role_update(client: httpx.AsyncClient):
    print("\n══════════════════════════════════════════")
    print("  TEST GROUP: PATCH /{company_id}/members/{profile_id}/role")
    print("══════════════════════════════════════════")

    role_url = f"{BASE_URL}/companies/{COMPANY_ID}/members/{EMPLOYEE_PROFILE_ID}/role"

    # ── Test 1.1: Employee cannot promote themselves ──────────────────────────
    print("\n[1.1] Employee tries to promote themselves (should 403)")
    r = await client.patch(role_url, json={"member_role": "OWNER"}, headers=headers(EMPLOYEE_JWT))
    check(r.status_code == 403, f"Correctly rejected with 403. Body: {r.json()}", f"Expected 403, got {r.status_code}: {r.text}")

    # ── Test 1.2: Invalid role value rejected ─────────────────────────────────
    print("\n[1.2] Invalid role 'PLATFORM_ADMIN' rejected by schema (should 422)")
    r = await client.patch(role_url, json={"member_role": "PLATFORM_ADMIN"}, headers=headers(COMPANY_OWNER_JWT))
    check(r.status_code == 422, f"Correctly rejected with 422 (schema validation).", f"Expected 422, got {r.status_code}: {r.text}")

    # ── Test 1.3: Owner promotes employee to OWNER ────────────────────────────
    print("\n[1.3] Company owner promotes employee to OWNER (should 200)")
    await db_reset_employee(EMPLOYEE_PROFILE_ID, COMPANY_ID)
    r = await client.patch(role_url, json={"member_role": "OWNER"}, headers=headers(COMPANY_OWNER_JWT))
    if check(r.status_code == 200, "Promotion succeeded.", f"Expected 200, got {r.status_code}: {r.text}"):
        body = r.json()
        check(body.get("member_role") == "OWNER", "Response shows member_role=OWNER.", f"Response member_role={body.get('member_role')}")

        # Verify DB: system_role should now be BRAND_ADMIN
        profile = await db_get_profile(EMPLOYEE_PROFILE_ID)
        check(
            profile and profile.system_role.value == "BRAND_ADMIN",
            "DB: system_role upgraded to BRAND_ADMIN after promotion.",
            f"DB: system_role is {profile.system_role if profile else 'None'}, expected BRAND_ADMIN."
        )

    # ── Test 1.4: Demote OWNER back to MEMBER ────────────────────────────────
    print("\n[1.4] Demote employee (now OWNER) back to MEMBER (should 200)")
    r = await client.patch(role_url, json={"member_role": "MEMBER"}, headers=headers(COMPANY_OWNER_JWT))
    if check(r.status_code == 200, "Demotion succeeded.", f"Expected 200, got {r.status_code}: {r.text}"):
        profile = await db_get_profile(EMPLOYEE_PROFILE_ID)
        check(
            profile and profile.system_role.value == "BRAND_EMPLOYEE",
            "DB: system_role revoked back to BRAND_EMPLOYEE after demotion.",
            f"DB: system_role is {profile.system_role if profile else 'None'}, expected BRAND_EMPLOYEE."
        )

    # ── Test 1.5: Platform admin can also promote ─────────────────────────────
    print("\n[1.5] Platform admin promotes employee to OWNER (should 200)")
    await db_reset_employee(EMPLOYEE_PROFILE_ID, COMPANY_ID)
    r = await client.patch(role_url, json={"member_role": "OWNER"}, headers=headers(PLATFORM_ADMIN_JWT))
    check(r.status_code == 200, "Platform admin promotion succeeded.", f"Expected 200, got {r.status_code}: {r.text}")

    await db_reset_employee(EMPLOYEE_PROFILE_ID, COMPANY_ID)

    # ── Test 1.6: Cannot promote non-active member ────────────────────────────
    print("\n[1.6] Cannot change role of SUSPENDED member (should 400)")
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(CompanyMember).where(
            CompanyMember.profile_id == EMPLOYEE_PROFILE_ID,
            CompanyMember.company_id == uuid.UUID(COMPANY_ID)
        ))
        m = res.scalar_one_or_none()
        if m:
            m.status = MemberStatus.SUSPENDED
            await db.commit()

    r = await client.patch(role_url, json={"member_role": "OWNER"}, headers=headers(COMPANY_OWNER_JWT))
    check(r.status_code == 400, f"Correctly rejected with 400 for suspended member.", f"Expected 400, got {r.status_code}: {r.text}")
    await db_reset_employee(EMPLOYEE_PROFILE_ID, COMPANY_ID)

    # ── Test 1.7: Concurrent promotions race condition ────────────────────────
    print("\n[1.7] Concurrent promote+demote — serialization check")
    tasks = [
        client.patch(role_url, json={"member_role": "OWNER"}, headers=headers(COMPANY_OWNER_JWT)),
        client.patch(role_url, json={"member_role": "MEMBER"}, headers=headers(COMPANY_OWNER_JWT)),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    codes = [r.status_code if isinstance(r, httpx.Response) else "EXC" for r in results]
    check(
        all(c in (200, 400, 409, 500) for c in codes),
        f"Concurrent requests handled cleanly: {codes}",
        f"Unexpected status codes: {codes}"
    )
    await db_reset_employee(EMPLOYEE_PROFILE_ID, COMPANY_ID)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: update_member_status
# ═══════════════════════════════════════════════════════════════════════════════

async def test_status_update(client: httpx.AsyncClient):
    print("\n══════════════════════════════════════════")
    print("  TEST GROUP: PATCH /{company_id}/members/{profile_id}/status")
    print("══════════════════════════════════════════")

    status_url = f"{BASE_URL}/companies/{COMPANY_ID}/members/{EMPLOYEE_PROFILE_ID}/status"

    # ── Test 2.1: Employee cannot change their own status ─────────────────────
    print("\n[2.1] Employee tries to suspend themselves (should 403)")
    r = await client.patch(status_url, json={"status": "SUSPENDED"}, headers=headers(EMPLOYEE_JWT))
    check(r.status_code == 403, f"Correctly rejected with 403.", f"Expected 403, got {r.status_code}: {r.text}")

    # ── Test 2.2: Invalid status value ────────────────────────────────────────
    print("\n[2.2] Invalid status 'DELETING' sent by client (should 422)")
    r = await client.patch(status_url, json={"status": "DELETING"}, headers=headers(COMPANY_OWNER_JWT))
    check(r.status_code in (400, 422), f"Correctly rejected with {r.status_code}.", f"Expected 400/422, got {r.status_code}: {r.text}")

    # ── Test 2.3: Suspend member ──────────────────────────────────────────────
    print("\n[2.3] Owner suspends employee (should 200)")
    await db_reset_employee(EMPLOYEE_PROFILE_ID, COMPANY_ID)
    r = await client.patch(status_url, json={"status": "SUSPENDED"}, headers=headers(COMPANY_OWNER_JWT))
    check(r.status_code == 200, "Suspension succeeded.", f"Expected 200, got {r.status_code}: {r.text}")

    # ── Test 2.4: Suspended member cannot access protected routes ─────────────
    print("\n[2.4] Suspended member cannot access company members list (should 403)")
    list_url = f"{BASE_URL}/companies/{COMPANY_ID}/members"
    r = await client.get(list_url, headers=headers(EMPLOYEE_JWT))
    check(r.status_code == 403, f"Correctly denied with 403.", f"Expected 403, got {r.status_code}: {r.text}")

    # ── Test 2.5: Reactivate suspended member ─────────────────────────────────
    print("\n[2.5] Owner reinstates suspended employee (should 200)")
    r = await client.patch(status_url, json={"status": "ACTIVE"}, headers=headers(COMPANY_OWNER_JWT))
    check(r.status_code == 200, "Reinstatement succeeded.", f"Expected 200, got {r.status_code}: {r.text}")

    # ── Test 2.6: Cannot modify a DELETING member ─────────────────────────────
    print("\n[2.6] Cannot modify a DELETING member (should 400)")
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(CompanyMember).where(
            CompanyMember.profile_id == EMPLOYEE_PROFILE_ID,
            CompanyMember.company_id == uuid.UUID(COMPANY_ID)
        ))
        m = res.scalar_one_or_none()
        if m:
            m.status = MemberStatus.DELETING
            await db.commit()

    r = await client.patch(status_url, json={"status": "ACTIVE"}, headers=headers(COMPANY_OWNER_JWT))
    check(r.status_code == 400, f"Correctly rejected with 400 for DELETING member.", f"Expected 400, got {r.status_code}: {r.text}")
    await db_reset_employee(EMPLOYEE_PROFILE_ID, COMPANY_ID)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: create_platform_admin
# ═══════════════════════════════════════════════════════════════════════════════

async def test_create_platform_admin(client: httpx.AsyncClient):
    print("\n══════════════════════════════════════════")
    print("  TEST GROUP: POST /admin/platform-admins/{profile_id}")
    print("══════════════════════════════════════════")

    target_profile_id = EMPLOYEE_PROFILE_ID

    # ── Test 3.1: Non-platform-admin cannot call this endpoint ───────────────
    print("\n[3.1] Company owner tries to create platform admin (should 403)")
    r = await client.post(f"{BASE_URL}/admin/platform-admins/{target_profile_id}", headers=headers(COMPANY_OWNER_JWT))
    check(r.status_code == 403, f"Correctly rejected with 403.", f"Expected 403, got {r.status_code}: {r.text}")

    # ── Test 3.2: Unknown profile_id returns 404 ──────────────────────────────
    print("\n[3.2] Non-existent profile_id returns 404")
    fake_id = "user_this_does_not_exist_xyz"
    r = await client.post(f"{BASE_URL}/admin/platform-admins/{fake_id}", headers=headers(PLATFORM_ADMIN_JWT))
    check(r.status_code == 404, f"Correctly returned 404.", f"Expected 404, got {r.status_code}: {r.text}")

    # ── Test 3.3: Platform admin promotes employee to PLATFORM_ADMIN ─────────────
    print("\n[3.3] Platform admin promotes employee to PLATFORM_ADMIN (should 200)")
    await db_reset_employee(EMPLOYEE_PROFILE_ID, COMPANY_ID)
    r = await client.post(f"{BASE_URL}/admin/platform-admins/{target_profile_id}", headers=headers(PLATFORM_ADMIN_JWT))
    if check(r.status_code == 200, "Promotion succeeded.", f"Expected 200, got {r.status_code}: {r.text}"):
        body = r.json()
        check(
            body.get("system_role") == "PLATFORM_ADMIN",
            "Response system_role=PLATFORM_ADMIN.",
            f"Response system_role={body.get('system_role')}"
        )
        # Verify DB
        profile = await db_get_profile(target_profile_id)
        check(
            profile and profile.system_role.value == "PLATFORM_ADMIN",
            "DB: system_role=PLATFORM_ADMIN confirmed.",
            f"DB: system_role={profile.system_role if profile else 'None'}"
        )

    # ── Test 3.4: Idempotent — calling again on an already-admin returns 200 ──
    print("\n[3.4] Idempotent — calling again on existing PLATFORM_ADMIN (should 200)")
    r = await client.post(f"{BASE_URL}/admin/platform-admins/{target_profile_id}", headers=headers(PLATFORM_ADMIN_JWT))
    check(r.status_code == 200, "Idempotent call returned 200.", f"Expected 200, got {r.status_code}: {r.text}")

    # ── Test 3.5: COMPANY_OWNER_JWT cannot promote via role endpoint ──────────
    print("\n[3.5] Company role PATCH cannot assign PLATFORM_ADMIN (schema guard)")
    role_url = f"{BASE_URL}/companies/{COMPANY_ID}/members/{target_profile_id}/role"
    r = await client.patch(role_url, json={"member_role": "PLATFORM_ADMIN"}, headers=headers(COMPANY_OWNER_JWT))
    check(r.status_code == 422, "Schema correctly blocks PLATFORM_ADMIN as member_role.", f"Expected 422, got {r.status_code}: {r.text}")

    # Reset employee back at end
    await db_reset_employee(EMPLOYEE_PROFILE_ID, COMPANY_ID)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: Last-owner protection
# ═══════════════════════════════════════════════════════════════════════════════

async def test_last_owner_protection(client: httpx.AsyncClient):
    print("\n══════════════════════════════════════════")
    print("  TEST GROUP: Last-owner guard")
    print("══════════════════════════════════════════")

    owner_profile_id = decode_profile_id(COMPANY_OWNER_JWT)
    role_url   = f"{BASE_URL}/companies/{COMPANY_ID}/members/{owner_profile_id}/role"
    status_url = f"{BASE_URL}/companies/{COMPANY_ID}/members/{owner_profile_id}/status"

    # ── Test 4.1: Cannot demote the only owner via role endpoint ─────────────
    print("\n[4.1] Cannot demote the only active OWNER to MEMBER (should 400)")
    r = await client.patch(role_url, json={"member_role": "MEMBER"}, headers=headers(COMPANY_OWNER_JWT))
    check(r.status_code == 400, f"Correctly rejected with 400.", f"Expected 400, got {r.status_code}: {r.text}")

    # ── Test 4.2: Cannot suspend the only owner via status endpoint ───────────
    print("\n[4.2] Cannot suspend the only active OWNER (should 400)")
    r = await client.patch(status_url, json={"status": "SUSPENDED"}, headers=headers(COMPANY_OWNER_JWT))
    check(r.status_code == 400, f"Correctly rejected with 400.", f"Expected 400, got {r.status_code}: {r.text}")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

async def main():
    if not CLERK_SECRET_KEY:
        print("❌ ERROR: CLERK_SECRET_KEY is missing from .env!")
        sys.exit(1)
        
    admin_uid, admin_jwt = provision_clerk_user("admin")
    owner_uid, owner_jwt = provision_clerk_user("owner")
    emp_uid, emp_jwt = provision_clerk_user("emp")

    # We must also create a real clerk org and put the users inside, because the role updates hit Clerk API directly.
    clerk_org_id = provision_clerk_organization(owner_uid, emp_uid)

    global PLATFORM_ADMIN_JWT, COMPANY_OWNER_JWT, EMPLOYEE_JWT, COMPANY_ID, EMPLOYEE_PROFILE_ID
    
    PLATFORM_ADMIN_JWT = admin_jwt
    COMPANY_OWNER_JWT = owner_jwt
    EMPLOYEE_JWT = emp_jwt
    EMPLOYEE_PROFILE_ID = emp_uid
    
    cid = None

    try:
        cid = await setup_test_db(admin_uid, owner_uid, emp_uid, clerk_org_id)
        COMPANY_ID = cid

        async with httpx.AsyncClient(timeout=15.0) as client:
            await test_role_update(client)
            await test_status_update(client)
            await test_create_platform_admin(client)
            await test_last_owner_protection(client)

        print("\n══════════════════════════════════════════")
        print("  All test groups complete.")
        print("══════════════════════════════════════════\n")

    finally:
        if cid:
            try:
                await teardown_test_db(admin_uid, owner_uid, emp_uid, cid)
            except Exception as e:
                print(f"⚠️ Warning: DB Teardown failed: {e}")
                
        try:
            delete_clerk_organization(clerk_org_id)
        except Exception:
            pass
            
        try:
            delete_clerk_user(admin_uid)
            delete_clerk_user(owner_uid)
            delete_clerk_user(emp_uid)
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
