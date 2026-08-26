import { NextRequest, NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { createClient as createServerClient } from '../../../../../../utils/supabase/server';
import { createServiceClient } from '../../../../../../utils/supabase/service';

export async function GET(req: NextRequest) {
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

    // 2. Fetch all promo codes (including inactive) — service client bypasses RLS
    const service = createServiceClient();
    const { data: promos, error } = await service
      .from('promo_codes')
      .select('*')
      .order('created_at', { ascending: false });

    if (error) {
      console.error('[admin/promo/list]', error);
      return NextResponse.json({ error: 'Failed to fetch promo codes.' }, { status: 500 });
    }

    return NextResponse.json({ promos });
  } catch (err) {
    console.error('[admin/promo/list] unexpected:', err);
    return NextResponse.json({ error: 'Internal server error.' }, { status: 500 });
  }
}

// PATCH — toggle active / deactivate a code
export async function PATCH(req: NextRequest) {
  try {
    const cookieStore = await cookies();
    const supabase = createServerClient(cookieStore);
    const { data: { user }, error: authError } = await supabase.auth.getUser();
    if (authError || !user) {
      return NextResponse.json({ error: 'Unauthorized.' }, { status: 401 });
    }

    const { data: profile } = await supabase.from('profiles').select('role').eq('id', user.id).single();
    if (profile?.role !== 'admin') {
      return NextResponse.json({ error: 'Forbidden — admin only.' }, { status: 403 });
    }

    const { id, is_active } = await req.json();
    if (!id) return NextResponse.json({ error: 'id is required.' }, { status: 400 });

    const service = createServiceClient();
    const { data, error } = await service
      .from('promo_codes')
      .update({ is_active })
      .eq('id', id)
      .select()
      .single();

    if (error) {
      return NextResponse.json({ error: 'Failed to update promo code.' }, { status: 500 });
    }

    return NextResponse.json({ success: true, promo: data });
  } catch (err) {
    console.error('[admin/promo/list PATCH] unexpected:', err);
    return NextResponse.json({ error: 'Internal server error.' }, { status: 500 });
  }
}
