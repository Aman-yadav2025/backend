-- 023_add_ready_to_ship_status.sql
-- Add READY_TO_SHIP to arrival_status enum.
-- This must be done outside a transaction block.

ALTER TYPE arrival_status ADD VALUE IF NOT EXISTS 'READY_TO_SHIP';
