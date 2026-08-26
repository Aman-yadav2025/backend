import { NextRequest, NextResponse } from 'next/server';
import Razorpay from 'razorpay';
import { cookies } from 'next/headers';
import { createClient as createServerClient } from '../../../../../utils/supabase/server';
import { createServiceClient } from '../../../../../utils/supabase/service';
import { PRICE_AMOUNTS } from '../../../../data/pricing';
import type { CapacityTier, SubscriptionPlanId } from '../../../../types/registration';

const razorpay = new Razorpay({
  key_id: process.env.RAZORPAY_KEY_ID!,
  key_secret: process.env.RAZORPAY_KEY_SECRET!,
});

export interface CreateOrderRequest {
  capacityTier: CapacityTier;
  plasticCapacityTier?: CapacityTier;
  metalCapacityTier?: CapacityTier;
  subscriptionPlan: SubscriptionPlanId;
  registrationType: 'brand' | 'recycler';
  materialCategory: 'plastic' | 'metal' | 'plastic_and_metal';
  promoCode?: string;
  companyInfo: {
    companyName: string;
    companyEmail: string;
    mobileNumber: string;
    gstNumber: string;
    panNumber: string;
    factoryAddress: string;
    state: string;
    city: string;
    pincode: string;
    companyWebsite: string;
    contactPerson: string;
    designation: string;
  };
}

export async function POST(req: NextRequest) {
  try {
    // 1. Auth
    const cookieStore = await cookies();
    const supabase = createServerClient(cookieStore);
    const { data: { user }, error: authError } = await supabase.auth.getUser();

    if (authError || !user) {
      return NextResponse.json(
        { error: 'Unauthorized — please sign in before completing payment.' },
        { status: 401 },
      );
    }

    // 2. Parse body
    const body: CreateOrderRequest = await req.json();
    const { capacityTier, plasticCapacityTier, metalCapacityTier, subscriptionPlan, registrationType, materialCategory, companyInfo, promoCode } = body;

    if ((!capacityTier && !plasticCapacityTier) || !subscriptionPlan || !companyInfo?.companyName) {
      return NextResponse.json({ error: 'Missing required fields.' }, { status: 400 });
    }

    // 3. Resolve base amount (if dual material, calculate from selected plastic and metal tiers)
    let originalAmount = 0;
    if (materialCategory === 'plastic_and_metal') {
      const plasticAmt = PRICE_AMOUNTS[plasticCapacityTier || capacityTier || 'tier2']?.[subscriptionPlan] || 0;
      const metalAmt = PRICE_AMOUNTS[metalCapacityTier || capacityTier || 'tier2']?.[subscriptionPlan] || 0;
      originalAmount = Math.max(plasticAmt, metalAmt) + Math.min(plasticAmt, metalAmt) / 2; // combined package pricing
    } else {
      originalAmount = PRICE_AMOUNTS[capacityTier]?.[subscriptionPlan] || 0;
    }

    if (!originalAmount || originalAmount <= 0) {
      return NextResponse.json(
        { error: 'Selected plan requires a custom quote. Please contact sales.' },
        { status: 400 },
      );
    }

    // 4. Apply promo code (re-validated server-side — never trust client amount)
    const service = createServiceClient();
    let discountAmount = 0;
    let validatedPromoCode: string | null = null;

    if (promoCode?.trim()) {
      const normalizedCode = promoCode.trim().toUpperCase();

      const { data: promo } = await service
        .from('promo_codes')
        .select('*')
        .eq('code', normalizedCode)
        .eq('is_active', true)
        .single();

      // Silently ignore invalid codes at order time — amount stays at original
      // (client already validated; this is a server-side safety re-check)
      if (
        promo &&
        (!promo.valid_until || new Date(promo.valid_until) >= new Date()) &&
        (promo.max_uses === null || promo.current_uses < promo.max_uses) &&
        (!promo.applicable_plans?.length || promo.applicable_plans.includes(subscriptionPlan)) &&
        (!promo.applicable_tiers?.length || promo.applicable_tiers.includes(capacityTier)) &&
        (!promo.applicable_roles?.length || promo.applicable_roles.includes(registrationType))
      ) {
        if (promo.discount_type === 'percentage') {
          discountAmount = Math.round((originalAmount * promo.discount_value) / 100);
        } else {
          discountAmount = Math.min(promo.discount_value, originalAmount);
        }
        validatedPromoCode = normalizedCode;
      }
    }

    const finalAmount = Math.max(originalAmount - discountAmount, 0);

    // 5. Create Razorpay order with final (discounted) amount
    const order = await razorpay.orders.create({
      amount: finalAmount,
      currency: 'INR',
      receipt: `reg_${user.id.slice(0, 8)}_${Date.now()}`,
      notes: {
        userId: user.id,
        companyName: companyInfo.companyName,
        plan: subscriptionPlan,
        tier: capacityTier,
        promoCode: validatedPromoCode ?? '',
      },
    });

    // 6. Upsert draft company row
    const { data: company, error: upsertError } = await service
      .from('companies')
      .upsert(
        {
          profile_id: user.id,
          name: companyInfo.companyName,
          email: companyInfo.companyEmail,
          mobile_number: companyInfo.mobileNumber,
          gst_number: companyInfo.gstNumber.toUpperCase(),
          pan_number: companyInfo.panNumber.toUpperCase(),
          factory_address: companyInfo.factoryAddress,
          state: companyInfo.state,
          city: companyInfo.city,
          pincode: companyInfo.pincode,
          website: companyInfo.companyWebsite || null,
          contact_person: companyInfo.contactPerson,
          designation: companyInfo.designation,
          registration_type: registrationType,
          material_category: materialCategory,
          capacity_tier: capacityTier,
          subscription_plan: subscriptionPlan,
          status: 'draft',
          razorpay_order_id: order.id,
          amount_paid: finalAmount,
          promo_code_used: validatedPromoCode,
          discount_amount: discountAmount,
        },
        { onConflict: 'profile_id' },
      )
      .select('id')
      .single();

    if (upsertError) {
      console.error('[create-order] upsert company error:', upsertError);
      return NextResponse.json({ error: 'Failed to save registration draft.' }, { status: 500 });
    }

    // 7. Create payment record
    const { error: paymentError } = await service.from('payments').insert({
      company_id: company.id,
      razorpay_order_id: order.id,
      amount: finalAmount,
      original_amount: originalAmount,
      discount_amount: discountAmount,
      promo_code: validatedPromoCode,
      currency: 'INR',
      status: 'created',
    });

    if (paymentError) {
      console.error('[create-order] insert payment error:', paymentError);
    }



    return NextResponse.json({
      orderId: order.id,
      amount: finalAmount,
      originalAmount,
      discountAmount,
      promoApplied: !!validatedPromoCode,
      currency: 'INR',
      companyId: company.id,
      keyId: process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID,
    });
  } catch (err) {
    console.error('[create-order] unexpected error:', err);
    return NextResponse.json({ error: 'Internal server error.' }, { status: 500 });
  }
}
