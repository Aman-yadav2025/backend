# Platform Backend (FastAPI)

Implements the core backend architecture using **FastAPI** (business logic), **Supabase PostgreSQL** (database), **Cloudflare R2** (document storage), **Razorpay** (payments), and **Clerk** (identity).

## 🚀 Comprehensive Feature Set

### 1. Identity & RBAC (Authentication)
- **Stateless Authentication**: Fast JWT validation via Clerk's JWKS.
- **Hierarchical Access Control**: Strong permission modeling for `PLATFORM_ADMIN`, `OWNER`, `ADMIN`, and `MEMBER`.
- **Profiles & Companies**: Complete onboarding flows for Brands and Recyclers, mapping Clerk users to internal profiles and company memberships.

### 2. Recycler & Brand Marketplace (B2B Deals)
- **Listings & Offers**: Recyclers can create material listings; Brands can accept them directly.
- **Unified Order History**: 
  - Recyclers can view `GET /listings/orders` for all incoming brand deals.
  - Brands can view `GET /listings/purchased-by-brands` for all their material purchases.
- **Status Lifecycle**: Built-in state machine for tracking deals (`purchase_status`, `arrival_status`).

### 3. Collector Purchases (Supply Chain)
- **Scrap Logging**: Recyclers can log incoming scrap purchases from informal waste collectors.
- **Advanced Filtering**: `GET /collector-purchases` supports robust search by `party_name`, `deal_status`, `min_amount`, `max_amount`, `start_date`, and `end_date`.

### 4. Recycler Dashboard & KPIs (Financial & Operational)
- **Collector Spend Summary**: Monthly aggregations of spending across categories.
- **Invoice Ledger**: A unified timeline of all financial invoices (Brand sales & Collector purchases) via `GET /kpis/invoice-ledger`. Supports advanced filtering by `invoice_no`, `deal_type`, `category`, `start_date`, etc.
- **Wallet Review**: Real-time aggregation of pending vs. received payments from Brands, including paginated lists of Brand invoices. Supports filtering by `company_name`, `status`, `invoice_no`, and `min_amount`/`max_amount`.
- **Operational Proofs (EPR)**: Specialized endpoints for tracking recycled utility metrics (electricity, water) and attaching proof documents.

### 5. Unified Document Vault (Cloudflare R2)
- **Secure File Storage**: Presigned URL generation for direct, secure client-side uploads and downloads.
- **Centralized Document API**: All company documents (Invoices, Utility Bills, Certificates) are queryable via `GET /documents`.
- **Advanced Search**: Filter documents by `document_name` (substring), `category` (enum), `start_date`, and `end_date`.

### 6. Payments & Wallets (Razorpay)
- **B2B Wallet Recharges**: Brands can recharge their internal platform wallets via Razorpay.
- **Webhooks**: Secure verification of Razorpay webhooks to automatically credit wallets on payment success.
- **Concurrency Locks**: Robust PostgreSQL row-level locks (`SELECT FOR UPDATE`) to prevent race conditions during checkouts, refunds, and wallet updates.

---

## 🛠️ Infrastructure Overview

1. **FastAPI Server**: Runs locally on `localhost:8000`.
2. **Redis**: Used for API rate-limiting via SlowAPI. Runs on `localhost:6379`.
3. **Database**: PostgreSQL hosted on **Supabase**.
4. **Storage**: Object Storage via **Cloudflare R2**.
5. **Webhooks/Tunnel**: **Ngrok** is required during local development to expose the localhost FastAPI server to the internet so that Clerk and Razorpay webhooks can reach it.

---

## 💻 Local Development Setup

### 1. Prerequisites
- Python 3.12+
- Redis running locally (`sudo apt install redis-server && sudo systemctl start redis`)
- Ngrok installed (`ngrok http 8000`)

### 2. Install Dependencies
```bash
python -m venv .venv 
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment Variables
You must create a `.env` file in the root of the `backend` folder.

1. Create a new file named `.env`.
2. Copy and paste the following template into the file and replace the placeholder values with your actual keys:

```env
# --- Database (Supabase) ----------------------------------------------------
# Use the connection string from your Supabase Project Settings > Database
DATABASE_URL=postgresql+asyncpg://postgres:[YOUR-PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres

# --- Clerk (Authentication) -------------------------------------------------
# Found in Clerk Dashboard > API Keys
CLERK_JWKS_URL=https://[YOUR-CLERK-URL]/.well-known/jwks.json
CLERK_ISSUER=https://[YOUR-CLERK-URL]
CLERK_WEBHOOK_SECRET=whsec_[YOUR-WEBHOOK-SECRET]
CLERK_SECRET_KEY=sk_test_[YOUR-SECRET-KEY]

# --- Razorpay (Payments) ----------------------------------------------------
# Found in Razorpay Dashboard > Settings > API Keys
RAZORPAY_KEY_ID=rzp_test_[YOUR-KEY-ID]
RAZORPAY_KEY_SECRET=[YOUR-KEY-SECRET]
RAZORPAY_WEBHOOK_SECRET=[YOUR-WEBHOOK-SECRET]

# --- Cloudflare R2 (Document Storage) ---------------------------------------
R2_ACCOUNT_ID=[YOUR-CLOUDFLARE-ACCOUNT-ID]
R2_ACCESS_KEY_ID=[YOUR-ACCESS-KEY]
R2_SECRET_ACCESS_KEY=[YOUR-SECRET-KEY]
R2_BUCKET_NAME=[YOUR-BUCKET-NAME]
R2_ENDPOINT_URL=https://[ACCOUNT-ID].r2.cloudflarestorage.com
R2_PRESIGNED_URL_EXPIRY_SECONDS=900
R2_MAX_UPLOAD_BYTES=52428800

# --- Redis (Rate Limiting) --------------------------------------------------
REDIS_URL=redis://localhost:6379

# --- App Settings -----------------------------------------------------------
INTERNAL_SERVICE_KEY=change-me-to-a-long-random-string
ENVIRONMENT=development
CORS_ORIGINS=http://localhost:5173
```

### 4. Cloudflare R2 Setup
To enable document uploads (invoices, utility bills):
1. Create a Bucket in Cloudflare R2.
2. Generate an API Token with `Object Read & Write` permissions.
3. Add the keys to `.env`:
   - `R2_ACCOUNT_ID`
   - `R2_ACCESS_KEY_ID`
   - `R2_SECRET_ACCESS_KEY`
   - `R2_BUCKET_NAME`

### 5. Ngrok & Webhooks (Crucial for Local Dev)
Because your backend runs on `localhost`, Clerk and Razorpay cannot send data to it. You must use Ngrok:
1. Start Ngrok in a separate terminal:
   ```bash
   ngrok http 8000
   ```
2. Copy the HTTPS URL provided by Ngrok (e.g., `https://abcd-123.ngrok-free.app`).
3. Update your Clerk Webhook Dashboard to point to `https://abcd-123.ngrok-free.app/webhooks/clerk`.
4. Update your Razorpay Webhook Dashboard to point to `https://abcd-123.ngrok-free.app/webhooks/razorpay`.

### 6. Start the Server
Run the database migrations:
```bash
# Execute SQL files in the /migrations folder directly in Supabase SQL editor or via psql.
```
Start FastAPI:
```bash
uvicorn app.main:app --reload
```

---

## 🧪 Testing & Utility Scripts

A robust suite of automation and testing scripts is provided in the `scripts/` directory to help with development and CI/CD pipelines.

### Automated End-to-End Tests
These scripts automatically provision temporary test accounts in Clerk, seed the local database, run through real HTTP lifecycles, and tear down everything:
- **`python scripts/test_marketplace.py`**: Tests the full B2B wallet checkout flow (recharge wallet via webhook → freeze funds on purchase → settle on delivery).
- **`python scripts/test_direct_payments.py`**: Tests the Direct Payment flow via Razorpay (create purchase → simulate `payment.failed` → simulate `order.paid` → verify confirmation).

### Unit & Integration Tests (Pytest)
Run the automated test suite using `pytest`:
- **`python -m pytest scripts/test_security_fixes.py`**: Validates JWT scoping, error masking, path traversal prevention, and pagination bounds.
- **`python -m pytest test_*.py`**: Root-level unit tests for KPI aggregates, webhook security, and database locking logic.

### Developer Utilities
- **`python scripts/provision_admin.py [user_id]`**: Bootstraps a specific Clerk user ID as a `PLATFORM_ADMIN` to bypass the UI and test protected admin routes.
- **`python scripts/simulate_razorpay_webhook.py [order_id] [pay_id]`**: Local testing tool that constructs and mathematically signs fake Razorpay payloads. Lets you test your webhook handlers without completing a real Razorpay checkout.
- **`python scripts/cleanup_bucket.py`**: Scans the Cloudflare R2 bucket against the Supabase database to find and safely delete orphaned document files. Safe by default (dry-run mode); run with `--confirm` to execute deletions.

---

## 🐳 Docker Production Setup (Recommended for Deployment)

For staging and production servers, the backend is fully dockerized to ensure consistent environments. 

### 1. Build the Docker Image
```bash
docker build -t b2b-platform-backend .
```

### 2. Run the Container
Ensure your `.env` file is fully populated (including your Supabase and Cloudflare credentials).

```bash
docker run -d \
  --name b2b-backend \
  -p 8000:8000 \
  --env-file .env \
  b2b-platform-backend
```
*Note: In production, Redis should be hosted on a dedicated service (e.g. AWS ElastiCache, Upstash, or a secondary Docker container) and `REDIS_URL` updated accordingly.*

---

## 📚 Comprehensive API Documentation
The backend generates dynamic, comprehensive API documentation using the OpenAPI standard.

To view the endpoints, request payloads, and schemas:
1. **Live Swagger UI**: Start the server and visit `http://localhost:8000/docs`.
2. **Markdown File**: Run `python scripts/generate_api_docs.py` to auto-generate an `api.md` file in the root directory.
