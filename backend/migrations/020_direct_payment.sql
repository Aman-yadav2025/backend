-- ============================================================================
-- 020_direct_payment.sql
-- Adds support for direct Razorpay payments on material purchases.
-- ============================================================================

-- 1. Extend the existing purchase_status enum with AWAITING_PAYMENT.
--    Postgres requires ALTER TYPE ... ADD VALUE; cannot be done inside a
--    transaction block, so we use a separate statement.
alter type purchase_status add value if not exists 'AWAITING_PAYMENT';

-- 2. New enum: payment_method
create type payment_method as enum ('WALLET', 'DIRECT');

-- 3. Add new columns to material_purchases
alter table material_purchases
    add column if not exists payment_method  payment_method not null default 'WALLET',
    add column if not exists razorpay_order_id   text,
    add column if not exists razorpay_payment_id text;

-- 4. Index for webhook lookup (razorpay_order_id → purchase row).
--    Partial index: only DIRECT purchases ever have an order_id.
create unique index if not exists idx_material_purchases_razorpay_order
    on material_purchases(razorpay_order_id)
    where razorpay_order_id is not null;
