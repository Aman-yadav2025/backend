-- ============================================================================
-- 012_material_tracking.sql
-- ============================================================================

-- 1. ENUMS
create type purchase_status as enum ('PENDING', 'CONFIRMED', 'CANCELLED');
create type arrival_status as enum ('PENDING', 'IN_TRANSIT', 'DELIVERED');

-- 2. TABLE: material_listings
create table material_listings (
  id uuid primary key default gen_random_uuid(),
  recycler_id uuid not null references companies(id) on delete cascade,
  type material_type not null,
  category text not null,
  grade text not null,
  -- Guard against zero/negative prices and quantities being inserted
  price_per_unit numeric(12, 2) not null check (price_per_unit > 0),
  total_quantity numeric(12, 2) not null check (total_quantity > 0),
  available_quantity numeric(12, 2) not null,
  validity_risk text,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint chk_available_quantity check (available_quantity >= 0 and available_quantity <= total_quantity)
);

create index idx_material_listings_recycler on material_listings(recycler_id);
create index idx_material_listings_active on material_listings(is_active) where is_active = true;

create trigger trg_material_listings_updated_at
  before update on material_listings
  for each row execute function set_updated_at();

-- 3. TABLE: material_purchases
create table material_purchases (
  id uuid primary key default gen_random_uuid(),
  listing_id uuid not null references material_listings(id) on delete restrict,
  brand_id uuid not null references companies(id) on delete restrict,
  category text not null,
  -- Guard against zero/negative quantities and prices
  purchased_quantity numeric(12, 2) not null check (purchased_quantity > 0),
  total_price numeric(12, 2) not null check (total_price > 0),
  purchase_type text not null,
  purchase_status purchase_status not null default 'PENDING',
  arrival_status arrival_status not null default 'PENDING',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_material_purchases_listing on material_purchases(listing_id);
create index idx_material_purchases_brand on material_purchases(brand_id);

create trigger trg_material_purchases_updated_at
  before update on material_purchases
  for each row execute function set_updated_at();

-- ============================================================================
-- 4. ROW LEVEL SECURITY
-- These tables hold sensitive commercial data. Access must be locked down.
-- The FastAPI backend operates with the service role and bypasses RLS entirely,
-- so these policies are defence-in-depth for any direct DB/Supabase SDK access.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- material_listings
-- Recyclers can manage their own listings.
-- Active (non-deleted) company members can read listings from any company
-- so that Brands can browse the marketplace.
-- ---------------------------------------------------------------------------
alter table material_listings enable row level security;
alter table material_listings force row level security;

-- Brands can browse active listings; recyclers can see their own (including inactive).
-- Competing recyclers must NOT be able to browse each other's pricing/inventory.
create policy material_listings_select
  on material_listings for select
  using (
    -- The recycler who owns this listing can always see it (active or inactive)
    recycler_id in (select auth_company_ids())
    -- Only active members of a BRAND company can browse active listings
    or (
      is_active = true
      and exists (
        select 1
        from company_members cm
        join companies c on c.id = cm.company_id
        where cm.profile_id = auth_profile_id()
          and cm.status = 'ACTIVE'
          and c.company_type = 'BRAND'
          and c.deleted_at is null
      )
    )
  );

-- Only a RECYCLER company admin can create/update/delete their own listings.
-- auth_is_company_admin alone is NOT enough — a Brand admin could pass their
-- own brand company_id as recycler_id and bypass the intent of this table.
create policy material_listings_insert
  on material_listings for insert
  with check (
    auth_is_company_admin(recycler_id)
    and exists (
      select 1 from companies c
      where c.id = recycler_id
        and c.company_type = 'RECYCLER'
        and c.deleted_at is null
    )
  );

create policy material_listings_update
  on material_listings for update
  using (
    auth_is_company_admin(recycler_id)
    and exists (
      select 1 from companies c
      where c.id = recycler_id
        and c.company_type = 'RECYCLER'
        and c.deleted_at is null
    )
  )
  with check (
    auth_is_company_admin(recycler_id)
    and exists (
      select 1 from companies c
      where c.id = recycler_id
        and c.company_type = 'RECYCLER'
        and c.deleted_at is null
    )
  );

create policy material_listings_delete
  on material_listings for delete
  using (
    auth_is_company_admin(recycler_id)
    and exists (
      select 1 from companies c
      where c.id = recycler_id
        and c.company_type = 'RECYCLER'
        and c.deleted_at is null
    )
  );

-- ---------------------------------------------------------------------------
-- material_purchases
-- Brands can see their own purchases.
-- Recyclers can see purchases made against their listings.
-- Neither side can see the other's unrelated commercial history.
-- ---------------------------------------------------------------------------
alter table material_purchases enable row level security;
alter table material_purchases force row level security;

-- Brand sees its own purchases. Recycler sees purchases on its listings.
create policy material_purchases_select
  on material_purchases for select
  using (
    brand_id in (select auth_company_ids())
    or exists (
      select 1 from material_listings ml
      where ml.id = material_purchases.listing_id
        and ml.recycler_id in (select auth_company_ids())
    )
  );

-- Only an active BRAND company member can create a purchase.
-- Must verify company_type='BRAND' — a Recycler could otherwise pass their
-- own recycler company_id as brand_id and create fake purchases.
create policy material_purchases_insert
  on material_purchases for insert
  with check (
    brand_id in (select auth_company_ids())
    and exists (
      select 1 from companies c
      where c.id = brand_id
        and c.company_type = 'BRAND'
        and c.deleted_at is null
    )
  );

-- Brands can cancel their pending purchases; recyclers can confirm/dispatch.
-- Actual status-transition logic is enforced in the FastAPI layer, not here.
create policy material_purchases_update
  on material_purchases for update
  using (
    brand_id in (select auth_company_ids())
    or exists (
      select 1 from material_listings ml
      where ml.id = material_purchases.listing_id
        and ml.recycler_id in (select auth_company_ids())
    )
  )
  -- WITH CHECK prevents updating brand_id or listing_id to a row the caller
  -- doesn't own, which would otherwise let a brand reassign another brand's
  -- purchase to itself.
  with check (
    brand_id in (select auth_company_ids())
    or exists (
      select 1 from material_listings ml
      where ml.id = material_purchases.listing_id
        and ml.recycler_id in (select auth_company_ids())
    )
  );
