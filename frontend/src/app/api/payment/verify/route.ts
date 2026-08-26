import { NextRequest, NextResponse } from 'next/server';
import crypto from 'crypto';
import { cookies } from 'next/headers';
import { createClient as createServerClient } from '../../../../../utils/supabase/server';
import { createServiceClient } from '../../../../../utils/supabase/service';

export interface VerifyPaymentRequest {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
  companyId: string;
}

export async function POST(req: NextRequest) {
  try {
    // 1. Auth check
    const cookieStore = await cookies();
    const supabase = createServerClient(cookieStore);
    const {
      data: { user },
      error: authError,
    } = await supabase.auth.getUser();

    if (authError || !user) {
      return NextResponse.json({ error: 'Unauthorized.' }, { status: 401 });
    }

    // 2. Parse body
    const body: VerifyPaymentRequest = await req.json();
    const { razorpay_order_id, razorpay_payment_id, razorpay_signature, companyId } = body;

    if (!razorpay_order_id || !razorpay_payment_id || !razorpay_signature || !companyId) {
      return NextResponse.json({ error: 'Missing payment fields.' }, { status: 400 });
    }

    // 3. Verify HMAC-SHA256 signature
    const keySecret = process.env.RAZORPAY_KEY_SECRET!;
    const expectedSignature = crypto
      .createHmac('sha256', keySecret)
      .update(`${razorpay_order_id}|${razorpay_payment_id}`)
      .digest('hex');

    if (expectedSignature !== razorpay_signature) {
      return NextResponse.json(
        { error: 'Payment signature verification failed. Possible tampering detected.' },
        { status: 400 },
      );
    }

    // 4. Use service client to update records (bypasses RLS)
    const service = createServiceClient();

    // Verify this company belongs to the authenticated user
    const { data: company, error: companyFetchError } = await service
      .from('companies')
      .select('id, profile_id')
      .eq('id', companyId)
      .single();

    if (companyFetchError || !company || company.profile_id !== user.id) {
      return NextResponse.json({ error: 'Company not found or access denied.' }, { status: 403 });
    }

    // 5. Update company: mark as pending_verification, store payment IDs
    const { error: companyUpdateError } = await service
      .from('companies')
      .update({
        status: 'pending_verification',
        razorpay_payment_id,
      })
      .eq('id', companyId);

    if (companyUpdateError) {
      console.error('[verify] company update error:', companyUpdateError);
      return NextResponse.json({ error: 'Failed to update company status.' }, { status: 500 });
    }

    // 6. Update payment record
    const { data: payment, error: paymentUpdateError } = await service
      .from('payments')
      .update({
        razorpay_payment_id,
        razorpay_signature,
        status: 'captured',
      })
      .eq('razorpay_order_id', razorpay_order_id)
      .select('promo_code')
      .single();

    if (paymentUpdateError) {
      // Non-fatal — company row is already updated; log and continue
      console.error('[verify] payment update error:', paymentUpdateError);
    } else if (payment?.promo_code) {
      // Increment promo usage counter atomically when payment is verified
      await service.rpc('increment_promo_usage', { p_code: payment.promo_code });
    }

    return NextResponse.json({ success: true, companyId });
  } catch (err) {
    console.error('[verify] unexpected error:', err);
    return NextResponse.json({ error: 'Internal server error.' }, { status: 500 });
  }
}
