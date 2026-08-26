-- ============================================================================
-- 014_company_wallet_and_epr.sql
-- Add wallet balance and required EPR credits to the companies table
-- ============================================================================

alter table companies
  add column wallet_balance numeric(12, 2) not null default 0.00 check (wallet_balance >= 0),
  add column epr_credits_required int not null default 0 check (epr_credits_required >= 0);

comment on column companies.wallet_balance is 'Prepaid wallet balance for marketplace purchases';
comment on column companies.epr_credits_required is 'The total EPR credits the brand/company is required to fulfill';
