-- Drop the existing unique constraint that applies to all rows
ALTER TABLE companies DROP CONSTRAINT IF EXISTS companies_owner_id_key;

-- Create a new unique index that only applies to active (non-deleted) companies
CREATE UNIQUE INDEX ix_companies_owner_id_unique ON companies (owner_id) WHERE deleted_at IS NULL;
