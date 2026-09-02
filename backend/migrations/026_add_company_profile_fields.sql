-- Migration to add Recycler Profile fields to the companies table
-- These are optional fields, primarily used by Recycler companies.

ALTER TABLE companies
    ADD COLUMN established_year INTEGER,
    ADD COLUMN cpcb_id TEXT,
    ADD COLUMN monthly_plant_capacity_mt INTEGER,
    ADD COLUMN esg_rating INTEGER,
    ADD COLUMN dispatch_lead_time_days TEXT;
