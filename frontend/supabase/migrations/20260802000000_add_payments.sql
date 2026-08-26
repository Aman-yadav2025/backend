-- Add Razorpay order/payment tracking columns to companies
alter table companies
  add column if not exists razorpay_order_id text unique,
  add column if not exists razorpay_payment_id text unique,
  add column if not exists amount_paid integer; -- in paise (INR × 100)

-- Payments table — immutable audit log of every Razorpay transaction
create table if not exists payments (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id) on delete cascade,
  razorpay_order_id text not null,
  razorpay_payment_id text,
  razorpay_signature text,
  amount integer not null,       -- in paise
  currency text not null default 'INR',
  status text not null default 'created', -- created | captured | failed
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now()
);

create index if not exists idx_payments_company_id on payments(company_id);
create index if not exists idx_payments_razorpay_order_id on payments(razorpay_order_id);

alter table payments enable row level security;

-- Users can read their own payment records
create policy "Users can view own payments" on payments
  for select to authenticated
  using (company_id in (select id from companies where profile_id = auth.uid()));

-- Only service-role (API routes) can insert/update payments — no client-side writes
create policy "Service role can manage payments" on payments
  for all to service_role
  using (true)
  with check (true);

-- updated_at trigger
create trigger update_payments_updated_at
  before update on payments
  for each row execute procedure update_updated_at_column();
