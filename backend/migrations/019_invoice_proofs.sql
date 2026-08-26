-- Migration: 019_invoice_proofs

DO $$ BEGIN
    CREATE TYPE invoice_proof_category AS ENUM (
        'ELECTRICITY',
        'WATER',
        'LOGISTICS',
        'FUEL'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

CREATE TABLE IF NOT EXISTS invoice_proofs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recycler_id UUID NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
    invoice_id UUID NOT NULL REFERENCES collector_purchases(id) ON DELETE RESTRICT,
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    document_name TEXT NOT NULL,
    category invoice_proof_category NOT NULL,
    period TEXT NOT NULL,
    unit_consumed NUMERIC(12, 2) NOT NULL DEFAULT 0,
    amount_spent NUMERIC(12, 2) NOT NULL DEFAULT 0,
    total_amount_used NUMERIC(12, 2) NOT NULL DEFAULT 0,
    total_amount_recycled NUMERIC(12, 2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_invoice_proofs_recycler_id ON invoice_proofs(recycler_id);
CREATE INDEX IF NOT EXISTS idx_invoice_proofs_invoice_id ON invoice_proofs(invoice_id);

-- Trigger to update updated_at
DROP TRIGGER IF EXISTS trigger_update_invoice_proofs_updated_at ON invoice_proofs;
CREATE TRIGGER trigger_update_invoice_proofs_updated_at
    BEFORE UPDATE ON invoice_proofs
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

-- RLS: A recycler can only see and manage its own proofs
ALTER TABLE invoice_proofs ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoice_proofs FORCE ROW LEVEL SECURITY;

CREATE POLICY invoice_proofs_all
  ON invoice_proofs FOR ALL
  USING (recycler_id IN (SELECT auth_company_ids()))
  WITH CHECK (recycler_id IN (SELECT auth_company_ids()));
