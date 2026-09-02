-- 024_add_withdrawals.sql
-- Adds bank account storage and withdrawal request tracking for Recyclers.

-- ── 1. Enum ──────────────────────────────────────────────────────────────────
CREATE TYPE withdrawal_status AS ENUM ('PENDING', 'APPROVED', 'REJECTED');

-- ── 2. Bank Accounts ─────────────────────────────────────────────────────────
-- Stores a recycler's saved bank or UPI payout destinations.
-- Either (account_number + ifsc_code) OR upi_id must be provided.
CREATE TABLE bank_accounts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id          UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,

    -- Bank transfer fields
    beneficiary_name    TEXT,
    account_number      TEXT,
    ifsc_code           TEXT,

    -- UPI field
    upi_id              TEXT,

    -- Optional: stored once we create the contact on RazorpayX in the future
    razorpay_contact_id     TEXT,
    razorpay_fund_account_id TEXT,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at          TIMESTAMPTZ,

    -- Must provide either bank details or UPI — not neither
    CONSTRAINT chk_bank_or_upi CHECK (
        (account_number IS NOT NULL AND ifsc_code IS NOT NULL AND beneficiary_name IS NOT NULL)
        OR (upi_id IS NOT NULL)
    )
);

CREATE INDEX idx_bank_accounts_company ON bank_accounts(company_id);

-- ── 3. Withdrawal Requests ────────────────────────────────────────────────────
-- Tracks each withdrawal request made by a Recycler.
CREATE TABLE withdrawal_requests (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id              UUID NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
    bank_account_id         UUID NOT NULL REFERENCES bank_accounts(id) ON DELETE RESTRICT,
    amount                  NUMERIC(14, 2) NOT NULL CHECK (amount > 0),
    status                  withdrawal_status NOT NULL DEFAULT 'PENDING',

    -- Admin fills this in when manually paying (UTR number, UPI ref, etc.)
    transaction_reference   TEXT,

    -- Audit trail
    actioned_by             TEXT REFERENCES profiles(id) ON DELETE SET NULL,
    actioned_at             TIMESTAMPTZ,

    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_withdrawal_requests_company ON withdrawal_requests(company_id);
CREATE INDEX idx_withdrawal_requests_status  ON withdrawal_requests(status);

-- ── 4. Row Level Security (RLS) ──────────────────────────────────────────────
ALTER TABLE bank_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE bank_accounts FORCE ROW LEVEL SECURITY;

CREATE POLICY bank_accounts_all
  ON bank_accounts FOR ALL
  USING (company_id IN (SELECT auth_company_ids()))
  WITH CHECK (company_id IN (SELECT auth_company_ids()));

ALTER TABLE withdrawal_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE withdrawal_requests FORCE ROW LEVEL SECURITY;

CREATE POLICY withdrawal_requests_all
  ON withdrawal_requests FOR ALL
  USING (company_id IN (SELECT auth_company_ids()))
  WITH CHECK (company_id IN (SELECT auth_company_ids()));
