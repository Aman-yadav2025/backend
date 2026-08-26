import { NextRequest, NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { createClient as createServerClient } from '../../../../../utils/supabase/server';
import { PRICE_AMOUNTS } from '../../../../data/pricing';
import type { CapacityTier, SubscriptionPlanId } from '../../../../types/registration';

export interface ValidatePromoRequest {
  code: string;
  capacityTier: CapacityTier;
  subscriptionPlan: SubscriptionPlanId;
  registrationType: 'brand' | 'recycler';
}

export interface ValidatePromoResponse {
  valid: boolean;
  discountType?: 'percentage' | 'flat';
  discountValue?: number;
  discountAmount?: number;   // paise saved
  finalAmount?: number;      // paise after discount
  originalAmount?: number;   // paise before discount
  description?: string;
  error?: string;
}

export async function POST(req: NextRequest) {
  try {
    // Must be signed in to validate
    const cookieStore = await cookies();
    const supabase = createServerClient(cookieStore);
    const { data: { user }, error: authError } = await supabase.auth.getUser();
    if (authError || !user) {
      return NextResponse.json({ valid: false, error: 'Unauthorized.' }, { status: 401 });
    }

    const body: ValidatePromoRequest = await req.json();
    const { code, capacityTier, subscriptionPlan, registrationType } = body;

    if (!code?.trim() || !capacityTier || !subscriptionPlan || !registrationType) {
      return NextResponse.json({ valid: false, error: 'Missing required fields.' }, { status: 400 });
    }

    const normalizedCode = code.trim().toUpperCase();

    // Fetch the promo code (RLS allows authenticated users to read active codes)
    const { data: promo, error: promoError } = await supabase
      .from('promo_codes')
      .select('*')
      .eq('code', normalizedCode)
      .eq('is_active', true)
      .single();

    if (promoError || !promo) {
      return NextResponse.json({ valid: false, error: 'Invalid or expired promo code.' });
    }

    // Check expiry
    if (promo.valid_until && new Date(promo.valid_until) < new Date()) {
      return NextResponse.json({ valid: false, error: 'This promo code has expired.' });
    }

    // Check validity window (not yet active)
    if (promo.valid_from && new Date(promo.valid_from) > new Date()) {
      return NextResponse.json({ valid: false, error: 'This promo code is not yet active.' });
    }

    // Check usage limit
    if (promo.max_uses !== null && promo.current_uses >= promo.max_uses) {
      return NextResponse.json({ valid: false, error: 'This promo code has reached its usage limit.' });
    }

    // Check plan restriction
    if (promo.applicable_plans && promo.applicable_plans.length > 0) {
      if (!promo.applicable_plans.includes(subscriptionPlan)) {
        return NextResponse.json({
          valid: false,
          error: `This code is only valid for: ${promo.applicable_plans.join(', ')} plan(s).`,
        });
      }
    }

    // Check tier restriction
    if (promo.applicable_tiers && promo.applicable_tiers.length > 0) {
      if (!promo.applicable_tiers.includes(capacityTier)) {
        return NextResponse.json({
          valid: false,
          error: `This code is only valid for: ${promo.applicable_tiers.join(', ')} tier(s).`,
        });
      }
    }

    // Check role restriction
    if (promo.applicable_roles && promo.applicable_roles.length > 0) {
      if (!promo.applicable_roles.includes(registrationType)) {
        return NextResponse.json({
          valid: false,
          error: `This code is only valid for: ${promo.applicable_roles.join(', ')}s.`,
        });
      }
    }

    // Resolve base amount
    const originalAmount = PRICE_AMOUNTS[capacityTier]?.[subscriptionPlan];
    if (!originalAmount || originalAmount <= 0) {
      return NextResponse.json({ valid: false, error: 'Promo codes cannot be applied to custom-quoted plans.' });
    }

    // Compute discount
    let discountAmount = 0;
    if (promo.discount_type === 'percentage') {
      discountAmount = Math.round((originalAmount * promo.discount_value) / 100);
    } else {
      discountAmount = Math.min(promo.discount_value, originalAmount);
    }

    const finalAmount = Math.max(originalAmount - discountAmount, 0);

    const response: ValidatePromoResponse = {
      valid: true,
      discountType: promo.discount_type,
      discountValue: promo.discount_value,
      discountAmount,
      finalAmount,
      originalAmount,
      description: promo.description ?? undefined,
    };

    return NextResponse.json(response);
  } catch (err) {
    console.error('[promo/validate]', err);
    return NextResponse.json({ valid: false, error: 'Internal server error.' }, { status: 500 });
  }
}
