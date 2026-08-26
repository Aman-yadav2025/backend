import { NextRequest, NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { createClient as createServerClient } from '../../../../../../utils/supabase/server';
import { createServiceClient } from '../../../../../../utils/supabase/service';

export interface CreatePromoRequest {
  code?: string;             // if blank, auto-generate
  discountType: 'percentage' | 'flat';
  discountValue: number;
  description?: string;
  maxUses?: number | null;
  validFrom?: string;        // ISO string
  validUntil?: string | null;
  applicablePlans?: string[];
  applicableTiers?: string[];
  applicableRoles?: string[];
}

/** Generates a random readable promo code like PNVR-A3KX9 */
function generateCode(): string {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  let segment = '';
  for (let i = 0; i < 5; i++) {
    segment += chars[Math.floor(Math.random() * chars.length)];
  }
  return `PNVR-${segment}`;
}

export async function POST(req: NextRequest) {
  try {
    // 1. Auth — must be admin
    const cookieStore = await cookies();
    const supabase = createServerClient(cookieStore);
    const { data: { user }, error: authError } = await supabase.auth.getUser();
    if (authError || !user) {
      return NextResponse.json({ error: 'Unauthorized.' }, { status: 401 });
    }

    const { data: profile } = await supabase
      .from('profiles')
      .select('role')
      .eq('id', user.id)
      .single();

    if (profile?.role !== 'admin') {
      return NextResponse.json({ error: 'Forbidden — admin only.' }, { status: 403 });
    }

    // 2. Parse body
    const body: CreatePromoRequest = await req.json();
    const {
      code,
      discountType,
      discountValue,
      description,
      maxUses,
      validFrom,
      validUntil,
      applicablePlans,
      applicableTiers,
      applicableRoles,
    } = body;

    // Validate
    if (!discountType || !discountValue) {
      return NextResponse.json({ error: 'discountType and discountValue are required.' }, { status: 400 });
    }
    if (discountType === 'percentage' && (discountValue <= 0 || discountValue > 100)) {
      return NextResponse.json({ error: 'Percentage discount must be between 1 and 100.' }, { status: 400 });
    }
    if (discountType === 'flat' && discountValue <= 0) {
      return NextResponse.json({ error: 'Flat discount must be a positive amount in paise.' }, { status: 400 });
    }

    // Resolve or generate code
    const finalCode = code?.trim().toUpperCase() || generateCode();

    // 3. Insert via service client
    const service = createServiceClient();
    const { data: promo, error: insertError } = await service
      .from('promo_codes')
      .insert({
        code: finalCode,
        discount_type: discountType,
        discount_value: discountValue,
        description: description || null,
        max_uses: maxUses ?? null,
        valid_from: validFrom || new Date().toISOString(),
        valid_until: validUntil || null,
        applicable_plans: applicablePlans?.length ? applicablePlans : null,
        applicable_tiers: applicableTiers?.length ? applicableTiers : null,
        applicable_roles: applicableRoles?.length ? applicableRoles : null,
        is_active: true,
        created_by: user.id,
      })
      .select()
      .single();

    if (insertError) {
      if (insertError.code === '23505') {
        return NextResponse.json({ error: `Code "${finalCode}" already exists. Use a different code.` }, { status: 409 });
      }
      console.error('[admin/promo/create]', insertError);
      return NextResponse.json({ error: 'Failed to create promo code.' }, { status: 500 });
    }

    return NextResponse.json({ success: true, promo }, { status: 201 });
  } catch (err) {
    console.error('[admin/promo/create] unexpected:', err);
    return NextResponse.json({ error: 'Internal server error.' }, { status: 500 });
  }
}
