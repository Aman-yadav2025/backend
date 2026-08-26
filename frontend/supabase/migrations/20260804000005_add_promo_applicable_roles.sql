-- Add applicable_roles column to promo_codes table
alter table promo_codes
  add column if not exists applicable_roles text[]; -- e.g. ARRAY['brand', 'recycler']
