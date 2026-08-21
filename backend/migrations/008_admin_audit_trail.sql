-- Migration 008: Add audit trail columns for admin actions
-- Tracks which admin performed document verification and refund request decisions.

-- Documents: who verified/rejected and when
ALTER TABLE documents
  ADD COLUMN verified_by TEXT REFERENCES profiles(id) ON DELETE RESTRICT,
  ADD COLUMN verified_at TIMESTAMPTZ;

-- Refund requests: who approved/rejected and when
ALTER TABLE refund_requests
  ADD COLUMN actioned_by TEXT REFERENCES profiles(id) ON DELETE RESTRICT,
  ADD COLUMN actioned_at TIMESTAMPTZ;
