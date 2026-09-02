-- Migration: 022_expand_company_epr_credits.sql
-- Adds epr_credits_purchased and epr_credits_utilized columns to companies,
-- and converts all 4 EPR columns from INTEGER to NUMERIC(12, 2) to support
-- fractional Metric Tons.

-- 1. Add the two new columns
ALTER TABLE companies
    ADD COLUMN IF NOT EXISTS epr_credits_purchased NUMERIC(12, 2) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS epr_credits_utilized  NUMERIC(12, 2) NOT NULL DEFAULT 0;

-- 2. Convert existing INTEGER columns to NUMERIC(12, 2)
ALTER TABLE companies
    ALTER COLUMN epr_credits_available TYPE NUMERIC(12, 2) USING epr_credits_available::NUMERIC,
    ALTER COLUMN epr_credits_required  TYPE NUMERIC(12, 2) USING epr_credits_required::NUMERIC;

-- 3. Constraints to keep all EPR values non-negative
ALTER TABLE companies
    ADD CONSTRAINT chk_company_epr_credits_available_positive  CHECK (epr_credits_available >= 0),
    ADD CONSTRAINT chk_company_epr_credits_purchased_positive  CHECK (epr_credits_purchased >= 0),
    ADD CONSTRAINT chk_company_epr_credits_utilized_positive   CHECK (epr_credits_utilized  >= 0);
