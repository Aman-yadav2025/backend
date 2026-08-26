-- Create custom enums for application domains
create type user_role as enum ('brand', 'recycler');
create type registration_type as enum ('brand', 'recycler');
create type material_category as enum ('plastic', 'metal');
create type capacity_tier as enum ('tier1', 'tier2', 'tier3', 'tier4');
create type subscription_plan as enum ('starter', 'growth', 'enterprise');
create type registration_status as enum ('draft', 'pending_verification', 'approved', 'rejected');
create type storage_provider as enum ('supabase', 'r2');
create type document_type as enum (
  'gst', 'pan', 'factory_license', 'pollution_cert', 'coi_cert', 
  'epr_cert', 'cancelled_cheque', 'auth_letter', 'recycler_cert'
);

-- Profiles table (extends Supabase Auth auth.users)
create table profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  role user_role not null,
  email text not null unique,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now()
);

-- Companies table (1-to-1 relationship with profile)
create table companies (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null unique references profiles(id) on delete cascade,
  name text not null,
  email text not null,
  mobile_number text not null,
  gst_number text not null unique,
  pan_number text not null unique,
  factory_address text not null,
  state text not null,
  city text not null,
  pincode text not null,
  website text,
  contact_person text not null,
  designation text not null,
  registration_type registration_type not null,
  material_category material_category not null,
  capacity_tier capacity_tier not null,
  subscription_plan subscription_plan not null,
  status registration_status not null default 'draft',
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now()
);

-- Documents table (tracks uploaded files with dynamic storage provider support)
create table documents (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id) on delete cascade,
  type document_type not null,
  file_name text not null,
  file_size text not null,
  file_type text not null,
  storage_provider storage_provider not null default 'supabase',
  storage_bucket text not null default 'compliance-documents',
  storage_path text not null unique,
  uploaded_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  
  constraint uq_company_document_type unique (company_id, type)
);

-- Automatically create a profile row in public schema upon auth.users signup
create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id, email, role)
  values (
    new.id,
    new.email,
    coalesce((new.raw_user_meta_data->>'role')::user_role, 'brand'::user_role)
  );
  return new;
end;
$$ language plpgsql security definer;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- Trigger helper to auto-update the updated_at timestamp columns
create or replace function update_updated_at_column()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

-- Apply updated_at triggers
create trigger update_profiles_updated_at before update on profiles for each row execute procedure update_updated_at_column();
create trigger update_companies_updated_at before update on companies for each row execute procedure update_updated_at_column();
create trigger update_documents_updated_at before update on documents for each row execute procedure update_updated_at_column();

-- Enable Row Level Security (RLS) on all exposed tables
alter table profiles enable row level security;
alter table companies enable row level security;
alter table documents enable row level security;

-- Row Level Security (RLS) Policies
-- Profiles policies
create policy "Users can view own profile" on profiles 
  for select to authenticated 
  using (auth.uid() = id);

create policy "Users can update own profile" on profiles 
  for update to authenticated 
  using (auth.uid() = id);

-- Companies policies
create policy "Users can view own company" on companies 
  for select to authenticated 
  using (profile_id = auth.uid());

create policy "Users can insert own company" on companies 
  for insert to authenticated 
  with check (profile_id = auth.uid());

create policy "Users can update own company" on companies 
  for update to authenticated 
  using (profile_id = auth.uid()) 
  with check (profile_id = auth.uid());

-- Documents policies
create policy "Users can view own company documents" on documents 
  for select to authenticated 
  using (company_id in (select id from companies where profile_id = auth.uid()));

create policy "Users can insert own company documents" on documents 
  for insert to authenticated 
  with check (company_id in (select id from companies where profile_id = auth.uid()));

create policy "Users can update own company documents" on documents 
  for update to authenticated 
  using (company_id in (select id from companies where profile_id = auth.uid()))
  with check (company_id in (select id from companies where profile_id = auth.uid()));

create policy "Users can delete own company documents" on documents 
  for delete to authenticated 
  using (company_id in (select id from companies where profile_id = auth.uid()));

-- Performance Indexes on Foreign Keys and Lookup Filters
create index idx_companies_profile_id on companies(profile_id);
create index idx_documents_company_id on documents(company_id);
create index idx_companies_status on companies(status);
create index idx_documents_type on documents(type);
