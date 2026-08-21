-- Add DELETING to member_status enum
ALTER TYPE member_status ADD VALUE IF NOT EXISTS 'DELETING';

-- Add deleted_at to companies
ALTER TABLE companies ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE DEFAULT NULL;

-- Add deleted_at to profiles
ALTER TABLE profiles ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE DEFAULT NULL;
