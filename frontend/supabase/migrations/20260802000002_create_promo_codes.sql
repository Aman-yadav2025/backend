-- Promo codes table
create table if not exists promo_codes (
  id uuid primary key default gen_random_uuid(),

  -- The code itself — uppercase, unique
  code text not null unique,

  -- Discount type: 'percentage' (e.g. 20 = 20% off) or 'flat' (e.g. 500000 = ₹5000 off in paise)
  discount_type text not null check (discount_type in ('percentage', 'flat')),

  -- Value: percentage 1-100, or flat amount in paise
  discount_value integer not null check (discount_value > 0),

  -- Optional: restrict to specific plans (null = all plans)
  applicable_plans text[], -- e.g. ARRAY['starter', 'growth']

  -- Optional: restrict to specific tiers (null = all tiers)
  applicable_tiers text[], -- e.g. ARRAY['tier1', 'tier2']

  -- Usage limits
  max_uses integer,          -- null = unlimited
  current_uses integer not null default 0,

  -- Validity window
  valid_from timestamp with time zone not null default now(),
  valid_until timestamp with time zone,    -- null = no expiry

  -- Soft-disable without deletion
  is_active boolean not null default true,

  -- Metadata
  description text,
  created_by uuid references profiles(id) on delete set null,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now()
);

-- Add promo tracking to companies and payments
alter table companies
  add column if not exists promo_code_used text references promo_codes(code) on delete set null,
  add column if not exists discount_amount integer default 0; -- discount in paise

alter table payments
  add column if not exists promo_code text references promo_codes(code) on delete set null,
  add column if not exists discount_amount integer default 0,
  add column if not exists original_amount integer; -- pre-discount amount in paise

-- Indexes
create index if not exists idx_promo_codes_code on promo_codes(code);
create index if not exists idx_promo_codes_is_active on promo_codes(is_active);
create index if not exists idx_promo_codes_valid_until on promo_codes(valid_until);

-- RLS
alter table promo_codes enable row level security;

-- Authenticated users can validate a code (read active codes only — no sensitive data exposed via API)
create policy "Authenticated users can read active promo codes" on promo_codes
  for select to authenticated
  using (is_active = true);

-- Only service-role can insert/update/delete (admin API routes use service client)
create policy "Service role manages promo codes" on promo_codes
  for all to service_role
  using (true)
  with check (true);

-- updated_at trigger
create trigger update_promo_codes_updated_at
  before update on promo_codes
  for each row execute procedure update_updated_at_column();
