# Backend Updates - August 20, 2026

This document summarizes all the backend updates, security hardening, and performance optimizations implemented today. The primary focus of this sprint was eliminating distributed systems race conditions, hardening the authentication layer against DoS attacks, and ensuring absolute data consistency across external services.

---

## 1. Security & Authentication Hardening (`security.py`)
The authentication layer (`SafeJWKSClient`) was significantly rewritten to protect against extreme edge cases and attacks:
* **Thundering Herd DoS Mitigation:** Implemented a rigorous Double-Checked Locking pattern (`asyncio.Lock()`) around the JWKS cache. When keys expire, exactly *one* task is allowed to cross the network boundary while all concurrent tasks wait and instantly utilize the resulting cache.
* **Cache-Poisoning & CancelledError Resilience:** FastAPI aggressively cancels tasks when clients disconnect (`asyncio.CancelledError`). We added a strict `finally` block to guarantee `_last_fetched` is updated even if a request is cancelled mid-flight, preventing the lock from becoming permanently poisoned.
* **Fail-Fast Session Protection:** If the Clerk JWKS endpoint experiences an outage, the system now tracks a `_fetch_failed` flag. Instead of aggressively failing with `401 Unauthorized` (which would force the frontend to wipe the user's session), it gracefully degrades to a `502 Bad Gateway`, preserving the session while safely rejecting unverified tokens.

## 2. TOCTOU (Time-Of-Check to Time-Of-Use) Race Condition Fixes
Previously, authorization was checked via FastAPI dependencies *before* the primary database transaction started. An attacker could initiate a destructive request, demote their own account privileges in another tab, and watch the destructive request succeed because it used stale auth data.
* **Resolution:** We pushed role re-verification directly into the Postgres `select(...).with_for_update()` transaction lock. 
* **Affected Files:**
  * `app/routers/documents.py` (`delete_document`)
  * `app/routers/companies.py` (`update_company`, `delete_company`)
  * `app/routers/payments.py` (`request_refund`)
  * `app/routers/company_members.py`

## 3. Distributed Systems Rollback Fix (`documents.py`)
* **Bug:** When deleting a document, the system deleted the physical file from Cloudflare R2 *before* committing the Postgres transaction. If the Postgres transaction rolled back (due to transient DB errors), the physical file was permanently gone but the database record remained, causing 404 crashes on subsequent lookups.
* **Fix:** The execution order was swapped. The system now executes `await db.delete(document)` and `await db.commit()` **first**. The R2 deletion is then executed inside a `try...except` block. If R2 fails, we safely leak a microscopic orphaned file rather than fatally corrupting the application state.

## 4. Webhook Escalation Patch (`clerk_webhooks.py`)
* **Bug:** The `_upsert_company_member` webhook automatically promoted the first user in any organization to global `SystemRole.BRAND_ADMIN`. If an organization was soft-deleted, a user could still trigger this webhook and escalate their global privileges via a defunct company.
* **Fix:** Added a `Company.deleted_at.is_(None)` guard check. Users joining soft-deleted companies are no longer eligible for global admin promotion.

## 5. Performance Optimizations (`migrations/006_performance_indexes.sql`)
Created a new database migration to add heavily optimized partial B-Tree indexes:
* **Active Hot-Path Indexes:** Added `deleted_at IS NULL` partial indexes on `companies` and `profiles` to dramatically speed up the `require_active_company_membership` check that runs on every authenticated request.
* **Background Sweeper Indexes:** Added `deleted_at IS NOT NULL` partial indexes. Background cron jobs sweeping for 30-day permanent deletions can now locate soft-deleted records instantly without scanning the 99% of active rows.
* **Admin Dashboard Indexes:** Added an index on `documents` where `status = 'PENDING_VERIFICATION'` so platform admins can instantly load document queues without scanning millions of verified documents.

## 6. Code Cleanup & Integrity
* Added missing `MemberRole` and `MemberStatus` imports in `payments.py` and `documents.py` to prevent runtime crashes during the new TOCTOU checks.
* Removed PEP-8 non-compliant inline imports (e.g., `DocumentStatus`) and promoted them to the top-level module imports.
