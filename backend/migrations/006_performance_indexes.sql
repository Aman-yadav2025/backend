-- ============================================================================
-- Migration 006: Performance & Soft-Delete Cleanup Indexes
-- Run this AFTER 005_refund_requests_razorpay_id.sql.
-- ============================================================================

-- 1. Active row fast-paths (Your suggestion)
-- Keeps the hot-path (require_active_company_membership) fast as tables grow,
-- excluding soft-deleted rows entirely from these indices.
CREATE INDEX idx_companies_active ON companies (id) WHERE deleted_at IS NULL;
CREATE INDEX idx_profiles_active ON profiles (id) WHERE deleted_at IS NULL;

-- 2. Soft-Delete Sweep Index (My suggestion)
-- Background workers (like deletion.py sweeping for 30-day permanent deletions)
-- will need to query for `deleted_at IS NOT NULL`. 
-- Since 99% of companies/profiles will be active, a partial index on IS NOT NULL 
-- will be microscopic (a few kilobytes) and make background cleanup queries lightning fast
-- without requiring a full table scan.
CREATE INDEX idx_companies_soft_deleted ON companies (deleted_at) WHERE deleted_at IS NOT NULL;
CREATE INDEX idx_profiles_soft_deleted ON profiles (deleted_at) WHERE deleted_at IS NOT NULL;

-- 3. Admin Verification Dashboard Index (My suggestion)
-- If Platform Admins ever need a global dashboard of all documents across the platform
-- that are awaiting manual review, this partial index instantly returns them 
-- without scanning the millions of already-verified documents.
CREATE INDEX idx_documents_pending_review ON documents (created_at) WHERE status = 'PENDING_VERIFICATION';
