-- ============================================================================
-- 015_wallet_recharge_and_marketplace.sql
-- 1. wallet_recharges — tracks Razorpay-backed wallet top-ups for brands
-- 2. companies.frozen_wallet_balance — ring-fenced amount for pending purchases
-- 3. material_purchases.pending_wallet_deduction — second-half owed on delivery
-- ============================================================================

-- ── 1. wallet_recharges ──────────────────────────────────────────────────────
create table wallet_recharges (
  id                       uuid        primary key default gen_random_uuid(),
  company_id               uuid        not null references companies(id) on delete restrict,
  initiated_by_profile_id  text        not null references profiles(id)  on delete restrict,
  razorpay_order_id        text        unique not null,
  razorpay_payment_id      text,
  razorpay_signature       text,
  -- PENDING → SUCCESS or FAILED (same state machine as payments)
  status                   text        not null default 'PENDING'
                             check (status in ('PENDING', 'SUCCESS', 'FAILED')),
  amount                   numeric(12, 2) not null check (amount > 0),
  currency                 text        not null default 'INR',
  created_at               timestamptz not null default now(),
  updated_at               timestamptz not null default now()
);

comment on table wallet_recharges is
  'Records every Razorpay-backed wallet top-up initiated by a Brand company. '
  'PENDING → SUCCESS credits wallet_balance. PENDING → FAILED rolls back '
  'the promo-lock equivalent (none here, but keeps the pattern consistent).';

create index idx_wallet_recharges_company   on wallet_recharges(company_id);
create index idx_wallet_recharges_order_id  on wallet_recharges(razorpay_order_id);

create trigger trg_wallet_recharges_updated_at
  before update on wallet_recharges
  for each row execute function set_updated_at();

-- RLS: A brand can only see its own recharge records.
alter table wallet_recharges enable row level security;
alter table wallet_recharges force row level security;

create policy wallet_recharges_select
  on wallet_recharges for select
  using (company_id in (select auth_company_ids()));

-- Only the backend service role inserts (no direct insert policy needed for
-- anon/authenticated roles — all writes go through the FastAPI service role).


-- ── 2. companies.frozen_wallet_balance ───────────────────────────────────────
-- The sum of all pending second-half amounts across active (PENDING) purchases.
-- Spendable balance = wallet_balance - frozen_wallet_balance.
-- Both columns are updated atomically inside a FOR UPDATE lock on the company row.
alter table companies
  add column frozen_wallet_balance numeric(12, 2) not null default 0.00
    check (frozen_wallet_balance >= 0);

comment on column companies.frozen_wallet_balance is
  'Ring-fenced wallet amount reserved for pending marketplace purchases. '
  'True spendable balance = wallet_balance - frozen_wallet_balance.';


-- ── 3. material_purchases.pending_wallet_deduction ───────────────────────────
-- The second-half amount (≈ total_price / 2) to be deducted from wallet_balance
-- when the brand confirms delivery. Set to 0 on CONFIRMED or CANCELLED.
alter table material_purchases
  add column pending_wallet_deduction numeric(12, 2) not null default 0.00
    check (pending_wallet_deduction >= 0);

comment on column material_purchases.pending_wallet_deduction is
  'Second-half payment owed on delivery confirmation. '
  'Mirrors the frozen amount held in companies.frozen_wallet_balance. '
  'Zeroed out when purchase is CONFIRMED or CANCELLED.';
