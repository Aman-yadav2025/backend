-- Migration 016: Offline Deals Support
-- Alters material_listings to allow offline deals uploaded by brands

BEGIN;

-- Make recycler_id optional
ALTER TABLE material_listings ALTER COLUMN recycler_id DROP NOT NULL;

-- Add created_by_brand_id to track which brand uploaded this offline deal
ALTER TABLE material_listings 
ADD COLUMN created_by_brand_id UUID REFERENCES companies(id) ON DELETE CASCADE;

-- Add offline_recycler_name to store the name of the un-onboarded recycler
ALTER TABLE material_listings 
ADD COLUMN offline_recycler_name TEXT;

-- Constraint: A listing must either belong to a registered recycler OR be an offline deal created by a brand
ALTER TABLE material_listings
ADD CONSTRAINT chk_recycler_or_offline 
CHECK (
    (recycler_id IS NOT NULL AND created_by_brand_id IS NULL AND offline_recycler_name IS NULL)
    OR
    (recycler_id IS NULL AND created_by_brand_id IS NOT NULL AND offline_recycler_name IS NOT NULL)
);

COMMIT;
