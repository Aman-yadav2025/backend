-- ============================================================================
-- Migration 003: Section 5 decisions
-- Run this AFTER 002_add_company_plan_fields.sql.
-- ============================================================================

-- --------------------------------------------------------------------------
-- 1. system_role: add PLATFORM_ADMIN
-- --------------------------------------------------------------------------
alter type system_role add value 'PLATFORM_ADMIN';

-- --------------------------------------------------------------------------
-- 2. payment_status: add refund statuses
-- --------------------------------------------------------------------------
alter type payment_status add value 'PENDING_REFUND';
alter type payment_status add value 'REFUNDED';
alter type payment_status add value 'PARTIALLY_REFUNDED';

-- --------------------------------------------------------------------------
-- 3. documents: add rejection_reason
-- --------------------------------------------------------------------------
alter table documents add column rejection_reason text;

-- --------------------------------------------------------------------------
-- 4. Create refund_requests table
-- --------------------------------------------------------------------------
create type refund_request_status as enum ('PENDING', 'APPROVED', 'REJECTED');

create table refund_requests (
  id                       uuid primary key default gen_random_uuid(),
  payment_id               uuid not null references payments(id) on delete restrict,
  requested_by_profile_id  text not null references profiles(id) on delete restrict,
  amount                   numeric(12, 2) not null check (amount > 0),
  status                   refund_request_status not null default 'PENDING',
  created_at               timestamptz not null default now(),
  updated_at               timestamptz not null default now()
);

create index idx_refund_requests_payment_id on refund_requests (payment_id);
create index idx_refund_requests_status on refund_requests (status);

create trigger trg_refund_requests_updated_at
  before update on refund_requests
  for each row execute function set_updated_at();

-- --------------------------------------------------------------------------
-- 5. RLS for refund_requests
-- --------------------------------------------------------------------------
alter table refund_requests enable row level security;
alter table refund_requests force row level security;

create policy refund_requests_select_company_admins
  on refund_requests for select
  using (
    exists (
      select 1 from payments p
      where p.id = refund_requests.payment_id
        and p.company_id in (select auth_company_ids())
        and auth_can_transact()
    )
  );

create policy refund_requests_insert_company_admins
  on refund_requests for insert
  with check (
    exists (
      select 1 from payments p
      where p.id = payment_id
        and p.company_id in (select auth_company_ids())
        and auth_can_transact()
    )
    and requested_by_profile_id = auth_profile_id()
  );

-- Backend (service role) handles updates to change status to APPROVED/REJECTED.
