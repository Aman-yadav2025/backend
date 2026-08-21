# Project Backend Context & Features

This document provides a comprehensive overview of the backend's capabilities, how each feature is structured, the available API endpoints, and instructions on how to use them. 

The backend is built with **FastAPI**, **SQLAlchemy (Async)**, **PostgreSQL**, **Clerk** (for Auth), **Cloudflare R2** (for document storage), and **Razorpay** (for payments).

---

## 1. Authentication, Sync & Role-Based Access Control (RBAC)
The platform uses Clerk as the identity provider. We never store passwords or handle login flows directly. Instead, we listen to Clerk Webhooks to mirror users and organizations into our Postgres database.

### API Endpoints
- `POST /webhooks/clerk`: Public webhook receiver for Clerk events.
  - Events handled: `user.created`, `user.updated`, `organization.created`, `organization.updated`, `organizationMembership.created`, `organizationMembership.updated`, `organizationMembership.deleted`.

### Security Dependencies (`app/security.py`)
All protected endpoints use FastAPI `Depends` to verify the JWT token passed in the `Authorization: Bearer <token>` header:
- `get_current_profile`: Authenticates any user and returns their `Profile`.
- `require_active_company_membership`: Ensures the user is an active member of the `company_id` specified in the path.
- `require_company_admin`: Ensures the user holds the `OWNER` role within the `company_id` specified in the path.
- `require_platform_admin`: Ensures the user holds the global `PLATFORM_ADMIN` system role.

---

## 2. Company & Employee Management
Companies (Brands or Recyclers) and their employees are grouped as organizations in Clerk. 

### Company Endpoints
- `GET /companies/me`: List all companies the current user is an active member of.
- `GET /companies/{company_id}`: Retrieve company details.
- `PATCH /companies/{company_id}/plan`: Lock-in endpoint used after signup to select whether the org is a `BRAND` or `RECYCLER` and select a tier. *Note: Once payments are made or documents uploaded, the company type is permanently locked.*
- `DELETE /companies/{company_id}`: Soft-deletes a brand. Requires `PLATFORM_ADMIN` or `BRAND_ADMIN`. 
  - **Feature**: Checks for pending payments to block deletion. If clear, it sets `deleted_at = now()` and spins up a background worker to asynchronously delete all employees from Clerk, the org from Clerk, and finally drops the data from the database.

### Employee Endpoints
- `GET /companies/{company_id}/members`: List all staff.
- `PATCH /companies/{company_id}/members/{profile_id}/status`: Suspend/Reinstate/Terminate a staff member (Admin only).
- `DELETE /companies/{company_id}/members/{profile_id}`: Targeted employee deletion.
  - **Feature**: Platform Admins can delete anyone, employees can delete themselves, and Brand Admins can manage their staff. If an admin deletes themselves and no other admin exists, they MUST provide `?promote_profile_id=<id>` to seamlessly hand over ownership before deletion.

---

## 3. Document Management & Verification
Documents (Compliance, Tax, Manifests) are stored in Cloudflare R2 securely. The backend never handles the binary files directly to save bandwidth; it issues presigned URLs.

### Document Upload Flow
1. `POST /documents/presign`: Client requests a secure upload URL.
   ```json
   { "file_name": "tax.pdf", "file_size_bytes": 1024, "file_type": "application/pdf", "category": "TAX" }
   ```
   **Feature**: Strict MIME type allowlist enforcing `.pdf`, `.png`, `.jpeg`, `.docx`, `.xlsx`.
2. Client uploads the file directly to R2 using the provided `upload_url`.
3. `POST /documents`: Client confirms upload, and the database creates a `Document` record in `PENDING_VERIFICATION` status.

### Document Management
- `GET /documents/{document_id}/url`: Generates a temporary, secure read-only presigned URL for viewing the file.
- `PUT /documents/{document_id}`: **Re-upload Feature.** If a document is rejected, the user can upload a new file to R2, call this endpoint with the new `storage_key`, and the document resets to `PENDING_VERIFICATION` (wiping the rejection reason).

### Admin Verification
- `PATCH /admin/documents/{document_id}/verify`: Platform Admin only.
  ```json
  { "status": "REJECTED", "rejection_reason": "Blurry image, please re-scan." }
  ```

---

## 4. Payments, Promos, & Refunds
Integrated natively with Razorpay for handling platform subscriptions and fees.

### Checkout & Webhooks
- `POST /payments/check-promo`: Validates a promo code and returns the exact calculated discount.
- `POST /payments/checkout`: 
  ```json
  { "plan_package": "GROWTH", "plan_tier": 2, "promo_code": "SUMMER20" }
  ```
  Creates a Razorpay Order ID and records a `PENDING` payment in the database.
- `POST /webhooks/razorpay`: Verifies the webhook signature. Upon `order.paid`, it idempotently marks the payment as `SUCCESS`.
  - **Promo Race Condition Lock**: Promo codes are permanently decremented *inside* this webhook. It uses `SELECT ... FOR UPDATE` to lock the promo row at the exact moment of payment success, guaranteeing max uses are never bypassed under high load.

### Promo Code Management
- `GET /promo-codes`: List all promo codes (Platform Admin only).
- `POST /promo-codes`: Create new promo codes (Percentage or Fixed amount).

### Refunds Architecture
1. `POST /payments/{payment_id}/refund-request`: A Brand Admin requests a refund. Records a `RefundRequest` in the DB and flips the payment status to `PENDING_REFUND`.
2. `GET /admin/refund-requests`: Platform Admin reviews requests.
3. `POST /admin/refund-requests/{refund_id}/approve`: Platform Admin approves the refund.
   - **Feature**: The backend makes a live API call to Razorpay (`razorpay_client.refund_payment()`) to process the funds immediately. Payment transitions to `REFUNDED`.
4. `POST /admin/refund-requests/{refund_id}/reject`: Denies the refund and restores the original `SUCCESS` payment status.

---

## 5. Background Task Archiving (Soft Deletes)
A robust background worker system (`app/services/deletion.py`) handles heavy-duty cascading deletions without blocking the HTTP response. 

**Code Snapshot: Background Brand Deletion**
```python
async def process_company_deletion_queue(company_id: uuid.UUID, clerk_org_id: str) -> None:
    async with AsyncSessionLocal() as session:
        # Loop through employees marked as 'DELETING'
        members = await session.execute(...)
        for member in members:
            await clerk_client.delete_user(member.profile_id) # Delete from Clerk Auth
            await session.delete(member) # Delete local record
            await asyncio.sleep(0.1) # Respect API limits
            
        await clerk_client.delete_organization(clerk_org_id)
        
        try:
            # Hard delete if possible
            await session.execute(delete(Company).where(Company.id == company_id))
        except Exception:
            # RESTRICT constraint catches if there are financial records (Payments).
            # We silently rollback, leaving the company "soft-deleted" forever 
            # to preserve the financial ledger!
            await session.rollback()
```
