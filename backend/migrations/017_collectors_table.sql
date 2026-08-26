-- Create collector_purchases table
CREATE TABLE collector_purchases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recycler_id UUID NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
    collector_name TEXT NOT NULL,
    collector_company_name TEXT NOT NULL,
    mobile_number TEXT NOT NULL,
    gst_number TEXT,
    address TEXT NOT NULL,
    category material_type NOT NULL, -- Enum created previously
    material_type TEXT NOT NULL,
    quantity NUMERIC(12, 2) NOT NULL,
    price NUMERIC(12, 2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    
    CONSTRAINT chk_collector_quantity_positive CHECK (quantity > 0),
    CONSTRAINT chk_collector_price_positive CHECK (price > 0)
);

CREATE INDEX idx_collector_purchases_recycler_id ON collector_purchases(recycler_id);

CREATE TRIGGER trg_collector_purchases_updated_at
  BEFORE UPDATE ON collector_purchases
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- RLS: A recycler can only see its own collector purchases.
ALTER TABLE collector_purchases ENABLE ROW LEVEL SECURITY;
ALTER TABLE collector_purchases FORCE ROW LEVEL SECURITY;

CREATE POLICY collector_purchases_select
  ON collector_purchases FOR SELECT
  USING (recycler_id IN (SELECT auth_company_ids()));
