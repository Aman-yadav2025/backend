-- ============================================================================
-- Production Platform Database Schema
-- PostgreSQL / Supabase
-- Auth identity: Clerk (JWT forwarded to Supabase, sub claim = Clerk user id)
-- ============================================================================
-- NOTES ON AUTH MODEL
-- --------------------------------------------------------------------------
-- Clerk handles identity, not Supabase Auth. To make Row Level Security (RLS)
-- work, Clerk must be configured to issue a JWT (via a Supabase JWT template)
-- that Supabase can verify. That JWT's `sub` claim will match profiles.id
-- (the Clerk user id, e.g. "user_2abc...").
--
-- The FastAPI backend should generally use the Supabase SERVICE ROLE key for
-- privileged operations (webhook processing, admin provisioning) which
-- bypasses RLS entirely -- RLS here is defense-in-depth for any path where a
-- client-issued (anon/authenticated) key touches the DB directly, e.g. via
-- Supabase client SDK calls from the frontend.
-- ============================================================================

-- ============================================================================
-- 0. EXTENSIONS
-- ============================================================================
create extension if not exists "pgcrypto";   -- gen_random_uuid()

-- ============================================================================
-- 1. ENUM TYPES
-- ============================================================================
create type system_role as enum ('RECYCLER', 'BRAND_ADMIN', 'BRAND_EMPLOYEE');
create type member_role as enum ('OWNER', 'MEMBER');
create type member_status as enum ('INVITED', 'ACTIVE', 'SUSPENDED', 'TERMINATED');
create type document_category as enum ('COMPLIANCE', 'TAX', 'RECYCLING_MANIFEST', 'OTHER');
create type document_status as enum ('PENDING_VERIFICATION', 'VERIFIED', 'REJECTED');
create type discount_type as enum ('PERCENTAGE', 'FIXED_AMOUNT');
create type payment_status as enum ('PENDING', 'SUCCESS', 'FAILED');

-- ============================================================================
-- 2. UPDATED_AT TRIGGER HELPER
-- ============================================================================
create or replace function set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- ============================================================================
-- 3. TABLE: profiles
-- Maps external Clerk user identities to internal system roles.
-- ============================================================================
create table profiles (
  id             text primary key,             -- Clerk user id, e.g. user_2abc...
  email          text not null unique,
  system_role    system_role not null,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);

create index idx_profiles_email on profiles (email);

create trigger trg_profiles_updated_at
  before update on profiles
  for each row execute function set_updated_at();

-- ============================================================================
-- 4. TABLE: companies
-- Stores organization and business identity data.
-- ============================================================================
create table companies (
  id                     uuid primary key default gen_random_uuid(),
  owner_id               text not null unique references profiles(id) on delete restrict,
  name                   text not null,
  gst_number             text,
  contact_person_name    text,
  contact_person_email   text,
  created_at             timestamptz not null default now(),
  updated_at             timestamptz not null default now()
);

create index idx_companies_owner_id on companies (owner_id);

create trigger trg_companies_updated_at
  before update on companies
  for each row execute function set_updated_at();

-- ============================================================================
-- 5. TABLE: company_members
-- Junction table mapping profiles to companies; manages B2B worker lifecycle.
-- ============================================================================
create table company_members (
  id             uuid primary key default gen_random_uuid(),
  company_id     uuid not null references companies(id) on delete cascade,
  profile_id     text not null references profiles(id) on delete cascade,
  member_role    member_role not null default 'MEMBER',
  status         member_status not null default 'INVITED',
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  constraint uq_company_profile unique (company_id, profile_id)
);

create index idx_company_members_company_id on company_members (company_id);
create index idx_company_members_profile_id on company_members (profile_id);
create index idx_company_members_status on company_members (status);

create trigger trg_company_members_updated_at
  before update on company_members
  for each row execute function set_updated_at();

-- ============================================================================
-- 6. TABLE: documents
-- Pointer ledger for files stored in Cloudflare R2.
-- ============================================================================
create table documents (
  id                       uuid primary key default gen_random_uuid(),
  company_id               uuid not null references companies(id) on delete cascade,
  uploaded_by_profile_id   text not null references profiles(id) on delete restrict,
  file_name                text not null,
  storage_key              text not null unique,
  file_size_bytes          bigint not null check (file_size_bytes >= 0),
  file_type                text not null,
  category                 document_category not null default 'OTHER',
  status                   document_status not null default 'PENDING_VERIFICATION',
  created_at               timestamptz not null default now(),
  updated_at               timestamptz not null default now()
);

create index idx_documents_company_id on documents (company_id);
create index idx_documents_uploaded_by on documents (uploaded_by_profile_id);
create index idx_documents_status on documents (status);

create trigger trg_documents_updated_at
  before update on documents
  for each row execute function set_updated_at();

-- ============================================================================
-- 7. TABLE: promo_codes
-- Tracks discount rules, concurrency limits, and redemption tallies.
-- ============================================================================
create table promo_codes (
  id                    uuid primary key default gen_random_uuid(),
  code                  text not null unique,
  discount_type         discount_type not null,
  discount_value        numeric(10, 2) not null check (discount_value > 0),
  max_uses              integer not null check (max_uses > 0),
  current_uses          integer not null default 0 check (current_uses >= 0),
  valid_from            timestamptz not null,
  valid_until           timestamptz not null,
  is_active             boolean not null default true,
  assigned_company_id   uuid references companies(id) on delete cascade,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now(),
  constraint chk_promo_validity_window check (valid_until > valid_from),
  constraint chk_promo_uses_within_max check (current_uses <= max_uses),
  constraint chk_percentage_bounds check (
    discount_type <> 'PERCENTAGE' or (discount_value > 0 and discount_value <= 100)
  )
);

create index idx_promo_codes_code on promo_codes (code);
create index idx_promo_codes_assigned_company on promo_codes (assigned_company_id);
create index idx_promo_codes_active_window on promo_codes (is_active, valid_from, valid_until);

create trigger trg_promo_codes_updated_at
  before update on promo_codes
  for each row execute function set_updated_at();

-- ============================================================================
-- 8. TABLE: payments
-- Financial ledger tracking the Razorpay checkout lifecycle.
-- ============================================================================
create table payments (
  id                       uuid primary key default gen_random_uuid(),
  company_id               uuid not null references companies(id) on delete restrict,
  initiated_by_profile_id  text not null references profiles(id) on delete restrict,
  razorpay_order_id        text not null unique,
  razorpay_payment_id      text,
  razorpay_signature       text,
  status                   payment_status not null default 'PENDING',
  original_amount          numeric(12, 2) not null check (original_amount >= 0),
  discount_amount          numeric(12, 2) not null default 0 check (discount_amount >= 0),
  amount_paid              numeric(12, 2) not null check (amount_paid >= 0),
  currency                 text not null default 'INR',
  applied_promo_id         uuid references promo_codes(id) on delete set null,
  created_at               timestamptz not null default now(),
  updated_at               timestamptz not null default now(),
  constraint chk_amount_paid_consistency check (amount_paid = original_amount - discount_amount)
);

create index idx_payments_company_id on payments (company_id);
create index idx_payments_status on payments (status);
create index idx_payments_promo_id on payments (applied_promo_id);

create trigger trg_payments_updated_at
  before update on payments
  for each row execute function set_updated_at();

-- ============================================================================
-- 9. SECURITY-DEFINER HELPER FUNCTIONS FOR RLS
-- These bypass RLS internally (SECURITY DEFINER) so policies can reference
-- them without infinite recursion, while still resolving identity from the
-- Clerk-issued JWT's `sub` claim.
-- ============================================================================

-- Current caller's profile id (Clerk user id) from the verified JWT.
create or replace function auth_profile_id()
returns text
language sql
stable
security definer
set search_path = public
as $$
  select nullif(current_setting('request.jwt.claims', true)::json->>'sub', '');
$$;

-- Current caller's system_role.
create or replace function auth_system_role()
returns system_role
language sql
stable
security definer
set search_path = public
as $$
  select system_role from profiles where id = auth_profile_id();
$$;

-- Company ids the current caller is an ACTIVE member of.
create or replace function auth_company_ids()
returns setof uuid
language sql
stable
security definer
set search_path = public
as $$
  select company_id
  from company_members
  where profile_id = auth_profile_id()
    and status = 'ACTIVE';
$$;

-- True if the current caller owns/administers the given company
-- (company owner, or an ACTIVE member with member_role = OWNER).
create or replace function auth_is_company_admin(target_company_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from companies c
    where c.id = target_company_id and c.owner_id = auth_profile_id()
  )
  or exists (
    select 1 from company_members cm
    where cm.company_id = target_company_id
      and cm.profile_id = auth_profile_id()
      and cm.status = 'ACTIVE'
      and cm.member_role = 'OWNER'
  );
$$;

-- True if the caller is allowed to execute financial transactions
-- (per README: only BRAND_ADMIN and RECYCLER system roles).
create or replace function auth_can_transact()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select auth_system_role() in ('RECYCLER', 'BRAND_ADMIN');
$$;

-- ============================================================================
-- 10. ROW LEVEL SECURITY
-- ============================================================================

-- ---------------------------------------------------------------------------
-- profiles
-- ---------------------------------------------------------------------------
alter table profiles enable row level security;
alter table profiles force row level security;

create policy profiles_select_self_or_org
  on profiles for select
  using (
    id = auth_profile_id()
    or exists (
      select 1 from company_members me
      join company_members them on them.company_id = me.company_id
      where me.profile_id = auth_profile_id()
        and me.status = 'ACTIVE'
        and them.profile_id = profiles.id
    )
  );

create policy profiles_update_self
  on profiles for update
  using (id = auth_profile_id())
  with check (id = auth_profile_id());

-- Inserts happen via the backend using the service role (on Clerk sign-up
-- webhook), so no public insert policy is defined here.

-- ---------------------------------------------------------------------------
-- companies
-- ---------------------------------------------------------------------------
alter table companies enable row level security;
alter table companies force row level security;

create policy companies_select_members
  on companies for select
  using (
    owner_id = auth_profile_id()
    or id in (select auth_company_ids())
  );

create policy companies_insert_owner
  on companies for insert
  with check (owner_id = auth_profile_id());

create policy companies_update_admin
  on companies for update
  using (auth_is_company_admin(id))
  with check (auth_is_company_admin(id));

-- ---------------------------------------------------------------------------
-- company_members
-- ---------------------------------------------------------------------------
alter table company_members enable row level security;
alter table company_members force row level security;

create policy company_members_select_own_org
  on company_members for select
  using (
    profile_id = auth_profile_id()
    or company_id in (select auth_company_ids())
    or auth_is_company_admin(company_id)
  );

create policy company_members_insert_admin
  on company_members for insert
  with check (auth_is_company_admin(company_id));

create policy company_members_update_admin
  on company_members for update
  using (auth_is_company_admin(company_id))
  with check (auth_is_company_admin(company_id));

create policy company_members_delete_admin
  on company_members for delete
  using (auth_is_company_admin(company_id));

-- ---------------------------------------------------------------------------
-- documents
-- ---------------------------------------------------------------------------
alter table documents enable row level security;
alter table documents force row level security;

create policy documents_select_org_members
  on documents for select
  using (company_id in (select auth_company_ids()));

create policy documents_insert_org_members
  on documents for insert
  with check (
    company_id in (select auth_company_ids())
    and uploaded_by_profile_id = auth_profile_id()
  );

create policy documents_update_admin_only
  on documents for update
  using (auth_is_company_admin(company_id))
  with check (auth_is_company_admin(company_id));

create policy documents_delete_admin_only
  on documents for delete
  using (auth_is_company_admin(company_id));

-- ---------------------------------------------------------------------------
-- promo_codes
-- Global codes (assigned_company_id is null) are readable by any
-- authenticated user; company-restricted codes are only readable by that
-- company's members. Writes are backend-only (service role).
-- ---------------------------------------------------------------------------
alter table promo_codes enable row level security;
alter table promo_codes force row level security;

create policy promo_codes_select_visible
  on promo_codes for select
  using (
    assigned_company_id is null
    or assigned_company_id in (select auth_company_ids())
  );

-- No insert/update/delete policies: promo code management is restricted to
-- the FastAPI backend using the service role key.

-- ---------------------------------------------------------------------------
-- payments
-- Only company admins/recyclers who can transact may view or create
-- payments for their own company; webhook updates run via service role.
-- ---------------------------------------------------------------------------
alter table payments enable row level security;
alter table payments force row level security;

create policy payments_select_company_admins
  on payments for select
  using (
    company_id in (select auth_company_ids())
    and auth_can_transact()
  );

create policy payments_insert_company_admins
  on payments for insert
  with check (
    company_id in (select auth_company_ids())
    and auth_can_transact()
    and initiated_by_profile_id = auth_profile_id()
  );

-- No update/delete policy: status transitions (PENDING -> SUCCESS/FAILED)
-- happen exclusively via the FastAPI Razorpay webhook handler using the
-- service role key, after verifying razorpay_signature.

-- ============================================================================
-- 11. RACE-SAFE PROMO REDEMPTION HELPER (used by backend, service role)
-- Encapsulates the SELECT ... FOR UPDATE pattern mentioned in the README so
-- redemption counting stays correct under concurrency.
-- ============================================================================
create or replace function redeem_promo_code(p_code text)
returns promo_codes
language plpgsql
as $$
declare
  v_promo promo_codes;
begin
  select * into v_promo
  from promo_codes
  where code = p_code
  for update;

  if not found then
    raise exception 'Promo code % not found', p_code;
  end if;

  if not v_promo.is_active then
    raise exception 'Promo code % is not active', p_code;
  end if;

  if now() < v_promo.valid_from or now() > v_promo.valid_until then
    raise exception 'Promo code % is outside its valid window', p_code;
  end if;

  if v_promo.current_uses >= v_promo.max_uses then
    raise exception 'Promo code % has reached its usage limit', p_code;
  end if;

  update promo_codes
  set current_uses = current_uses + 1
  where id = v_promo.id
  returning * into v_promo;

  return v_promo;
end;
$$;
