# Platform Backend (FastAPI)

Implements the architecture in the original README: Clerk (identity) →
FastAPI (business logic) → Postgres/Supabase (state) → Cloudflare R2
(documents) → Razorpay (payments).

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in real values
```

Run the DB migrations (`migrations/001_initial_schema.sql`, then
`migrations/002_add_company_plan_fields.sql`) against your Postgres/Supabase
instance before starting the app.

```bash
uvicorn app.main:app --reload
```

## Request flow summary

- **Auth**: every request (except the two webhook endpoints) carries a
  Clerk session JWT as `Authorization: Bearer <token>`. `app/security.py`
  verifies it against Clerk's JWKS and resolves it to a `profiles` row.
- **Identity sync**: `POST /webhooks/clerk` handles `user.created/updated`,
  `organization.created`, and `organizationMembership.*` events to keep
  `profiles`, `companies`, and `company_members` in sync with Clerk. Org
  creation is 1:1 — an org's creator becomes the company `owner_id` and an
  `OWNER` `company_members` row, per your answer.
- **Documents**: `POST /companies/{id}/documents/presign` returns an R2
  presigned PUT URL; the client uploads directly to R2; then
  `POST /companies/{id}/documents` writes the pointer row.
- **Payments**: `POST /companies/{id}/payments/checkout` looks up the
  company's own `pack`/`tier`, prices it via the fixed matrix in
  `app/pricing.py`, optionally locks and applies a promo code
  (`SELECT ... FOR UPDATE`), creates a Razorpay order, and stores a
  `PENDING` payment row. `POST /webhooks/razorpay` (the `order.paid` event)
  is the actual source of truth that flips it to `SUCCESS` — the
  `/verify` endpoint is just a fast client-side UX confirmation.

## Flagged assumptions / open questions (please confirm or correct)

1. **`companies.id` vs Clerk org id** — Clerk organization ids are strings
   (`org_...`), not UUIDs, but every FK in the schema points at
   `companies.id` (UUID). I added a separate `clerk_org_id text unique`
   column (migration 002) instead of changing the PK type. Confirm this is
   acceptable, or tell me if you'd rather use the Clerk org id as the PK
   directly (would require retyping every FK column across the schema).

2. **New company's default `company_type`/`pack`/`tier`** — when
   `organization.created` fires, I default every new company to
   `BRAND` / `STARTER` / tier `1` (see `clerk_webhooks.py`). The README
   doesn't say how a brand-new signup picks its type/pack/tier — is this
   chosen during a signup form, or always this default until the first
   payment upgrades it?

3. **Promo code management has no owning role** — `system_role` only has
   `RECYCLER`, `BRAND_ADMIN`, `BRAND_EMPLOYEE`; none of these is a
   platform-level admin who should be allowed to create/deactivate promo
   codes globally. I gated `/admin/promo-codes/*` behind a shared
   `X-Internal-Key` header (`INTERNAL_SERVICE_KEY` in `.env`) as a
   placeholder. Replace with a real role check once one exists.

4. **Document `VERIFIED`/`REJECTED` workflow** — left out of this pass per
   your answer. The `documents` table and status enum already support it;
   just needs a `PATCH /{document_id}/status` endpoint plus a decision on
   who can call it.

5. **Failed payments don't roll back promo redemption** — if a promo code
   was applied at checkout and the payment later fails
   (`payment.failed` webhook), `promo_codes.current_uses` is NOT
   decremented (see comment in `razorpay_webhooks.py`). Confirm whether a
   failed payment should free up that redemption slot.

6. **Company member invites** — per the original README, employee invites
   go through Clerk's own org-invite UI/API, not a custom endpoint here.
   The corresponding `company_members` row is created automatically by the
   `organizationMembership.created` webhook. Confirm that's the intended
   flow (vs. a custom invite endpoint that also sends its own email).

7. **Pricing numbers in `app/pricing.py` are placeholders** — replace the
   12 package×tier amounts with your real prices before going live.

## Not implemented (explicitly out of scope per your instructions)

- KPI endpoints/aggregations — you said later stage, not now.
