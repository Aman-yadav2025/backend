-- 025_add_tds_fields.sql
-- Adds Technical Data Sheet (TDS) fields and MOQ to material listings.

ALTER TABLE material_listings
    ADD COLUMN description TEXT,
    ADD COLUMN batch_inspection_report TEXT,
    ADD COLUMN min_order_quantity NUMERIC(12, 2),
    ADD COLUMN carbon_reduction_per_kg NUMERIC(12, 2),
    ADD COLUMN water_conservation_per_kg NUMERIC(12, 2),
    ADD COLUMN accreditations TEXT[] DEFAULT '{}',
    ADD COLUMN technical_parameters JSONB DEFAULT '{}'::jsonb;

-- Ensure that min_order_quantity is valid (if provided, it must be > 0 and <= total_quantity)
ALTER TABLE material_listings
    ADD CONSTRAINT chk_min_order_quantity 
    CHECK (min_order_quantity IS NULL OR (min_order_quantity > 0 AND min_order_quantity <= total_quantity));
