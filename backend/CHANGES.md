# Section 5 Decisions & Follow-ups Changelog

This document summarizes the backend implementations completed based on the "Section 5 Open Questions" decisions.

## 1. Database Migrations & Schemas
- **[NEW] `migrations/003_section_5_decisions.sql`**: Added `PLATFORM_ADMIN` to `system_role`, new refund statuses (`PENDING_REFUND`, `REFUNDED`, `PARTIALLY_REFUNDED`), the `rejection_reason` column to `documents`, and created the `refund_requests` table with corresponding Row Level Security (RLS) policies.
- **[MODIFY] `app/models.py` & `app/schemas.py`**: Updated SQLAlchemy models and Pydantic schemas to align with the new migration (adding the `RefundRequest` model, the new enums, and request schemas).

## 2. Security & Role Management
- **[MODIFY] `app/config.py`**: Completely removed the deprecated `internal_service_key`.
- **[MODIFY] `app/security.py`**: Dropped `require_internal_service` and implemented `require_platform_admin` which checks for the actual `PLATFORM_ADMIN` role.
- **[MODIFY] `app/routers/promo_codes.py`**: Swapped all internal key checks on promo admin endpoints to use the new `require_platform_admin` dependency.

## 3. Refunds Architecture
- **[MODIFY] `app/services/razorpay_client.py`**: Added a new `refund_payment()` method to natively call the Razorpay API.
- **[MODIFY] `app/routers/payments.py`**: Created `POST /{payment_id}/refund-request` (gated to company admins), which records the requested refund amount, creates a `RefundRequest` record, and flips the payment status to `PENDING_REFUND`.
- **[NEW] `app/routers/admin.py`**: Created the new platform admin router and added:
  - `GET /refund-requests` to list pending requests.
  - `POST /refund-requests/{id}/approve` to programmatically trigger the Razorpay API refund and mark the request as approved.
  - `POST /refund-requests/{id}/reject` to reject the refund and gracefully restore the payment status.
- **[MODIFY] `app/main.py`**: Wired up the new `admin.py` router.

## 4. Promo Race Condition Fix
- **[MODIFY] `app/routers/payments.py`**: Removed the `SELECT ... FOR UPDATE` lock and increment logic from the checkout phase, replacing it with a soft-check that calculates the discount instantly.
- **[MODIFY] `app/routers/razorpay_webhooks.py`**: Moved the `SELECT ... FOR UPDATE` lock and `current_uses += 1` logic into the `order.paid` webhook under a single database transaction. This guarantees that race conditions can't happen on payment success, while keeping checkout perfectly fast.

## 5. Document Verification & Re-upload
- **[MODIFY] `app/routers/documents.py`**:
  - Enforced a strict server-side file extension and MIME type allowlist (`.pdf`, `.jpg`, `.jpeg`, `.png`, `.docx`, `.xlsx`) on the `POST /presign` endpoint.
  - Added a `PUT /{document_id}` endpoint that securely replaces a document's pointer after re-upload, automatically resetting its status to `PENDING_VERIFICATION` and clearing any previous rejection reason.
- **[MODIFY] `app/routers/admin.py`**: Added `PATCH /documents/{id}/verify` for the platform admin to accept or reject documents (capturing a rejection reason).

## 6. Company Role Lock-in
- **[MODIFY] `app/routers/companies.py`**: Added `PATCH /{company_id}/plan` to allow newly created organizations to solidify their `company_type` (Brand vs. Recycler), `pack`, and `tier`. Added a strict validation check preventing users from swapping their `company_type` once they have made payments or uploaded documents.

## 7. Deletion & Background Archiving
- **[NEW] `app/services/clerk_client.py`**: Created a REST API client to handle direct identity deletion calls to Clerk via `CLERK_SECRET_KEY`.
- **[NEW] `migrations/004_soft_deletes.sql`**: Added `deleted_at` to `companies` and `profiles`, and introduced a `DELETING` status to `MemberStatus` without dropping any foreign key constraints.
- **[MODIFY] `app/routers/companies.py` & `app/routers/company_members.py`**: 
  - Updated API queries to natively filter out companies where `deleted_at IS NOT NULL`.
  - Added `DELETE /companies/{company_id}` for protected brand deletion. Blocks deletion if any `PENDING` or `PENDING_REFUND` payments exist.
  - Added `DELETE /companies/{company_id}/members/{profile_id}` for targeted employee deletion, including safeguards enforcing that at least one admin must always exist.
- **[NEW] `app/services/deletion.py`**: Implemented the asynchronous background queueing system to handle complex cascading deletions. It loops through locked employees, deletes identities from Clerk, and carefully removes database records. It automatically preserves financial integrity by falling back to a permanent soft-delete if `ON DELETE RESTRICT` constraints block a final company deletion.
