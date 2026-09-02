-- Add new categories to document_category enum
ALTER TYPE document_category ADD VALUE IF NOT EXISTS 'GST_CERTIFICATE';
ALTER TYPE document_category ADD VALUE IF NOT EXISTS 'PAN_CARD';
ALTER TYPE document_category ADD VALUE IF NOT EXISTS 'FACTORY_LICENSE';
ALTER TYPE document_category ADD VALUE IF NOT EXISTS 'CERTIFICATE_OF_INCORPORATION';
ALTER TYPE document_category ADD VALUE IF NOT EXISTS 'EPR_CERTIFICATE';
ALTER TYPE document_category ADD VALUE IF NOT EXISTS 'CANCELLED_CHEQUE';

ALTER TABLE collector_purchases
    ADD COLUMN IF NOT EXISTS created_by_profile_id TEXT
        REFERENCES profiles(id) ON DELETE RESTRICT;
CREATE INDEX IF NOT EXISTS idx_collector_purchases_created_by
    ON collector_purchases (created_by_profile_id);

