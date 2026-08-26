-- Atomic increment of promo code usage counter.
-- Called by the API service-role after a successful order creation.
create or replace function public.increment_promo_usage(p_code text)
returns void
language plpgsql
security definer
as $$
begin
  update public.promo_codes
  set current_uses = current_uses + 1
  where code = p_code;
end;
$$;
