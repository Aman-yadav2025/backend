-- ============================================================================
-- Migration 002: company plan/type fields + payment plan snapshot
-- Run this AFTER schema.sql (migration 001 / initial schema).
-- ============================================================================

create type company_type as enum ('BRAND', 'RECYCLER');
create type pack_type as enum ('STARTER', 'GROWTH', 'ENTERPRISE');

-- --------------------------------------------------------------------------
-- companies: add Clerk org linkage + type/pack/tier (drives pricing)
-- --------------------------------------------------------------------------
alter table companies
  add column clerk_org_id  text unique,
  add column company_type  company_type not null default 'BRAND',
  add column pack          pack_type not null default 'STARTER',
  add column tier          integer not null default 1;

alter table companies
  add constraint chk_company_tier_range check (tier between 1 and 4);

-- Drop the defaults now that existing rows are backfilled; new inserts must
-- specify these explicitly going forward.
alter table companies alter column company_type drop default;
alter table companies alter column pack drop default;
alter table companies alter column tier drop default;

create index idx_companies_clerk_org_id on companies (clerk_org_id);

-- --------------------------------------------------------------------------
-- payments: snapshot which package/tier was actually purchased
-- (companies.pack/tier can change later; payments must not drift with it)
-- --------------------------------------------------------------------------
alter table payments
  add column plan_package pack_type not null default 'STARTER',
  add column plan_tier    integer not null default 1;

alter table payments
  add constraint chk_payment_plan_tier_range check (plan_tier between 1 and 4);

alter table payments alter column plan_package drop default;
alter table payments alter column plan_tier drop default;
