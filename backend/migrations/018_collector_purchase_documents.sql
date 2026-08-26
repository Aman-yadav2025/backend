-- Alter DocumentCategory enum to add COLLECTOR_RECEIPT
ALTER TYPE document_category ADD VALUE IF NOT EXISTS 'COLLECTOR_RECEIPT';

-- Add document_id to collector_purchases
ALTER TABLE collector_purchases 
ADD COLUMN document_id UUID REFERENCES documents(id) ON DELETE SET NULL;

-- Add index on the new foreign key
CREATE INDEX idx_collector_purchases_document_id ON collector_purchases(document_id);
