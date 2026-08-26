import { type NextRequest, NextResponse } from 'next/server';
import { createServerClient } from '@supabase/ssr';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '';

export async function middleware(request: NextRequest) {
  let supabaseResponse = NextResponse.next({ request });

  if (!supabaseUrl || !supabaseKey) {
    return supabaseResponse;
  }

  try {
    const supabase = createServerClient(supabaseUrl, supabaseKey, {
      cookies: {
        getAll() { return request.cookies.getAll(); },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
          supabaseResponse = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options),
          );
        },
      },
    });

    // Always refresh session first — required by Supabase SSR
    const { data: { user } } = await supabase.auth.getUser();
    const { pathname } = request.nextUrl;

    // ── Brand dashboard guard ────────────────────────────────────────────────────
    if (pathname.startsWith('/brand/dashboard')) {
      if (!user) {
        const url = request.nextUrl.clone();
        url.pathname = '/brand/login';
        url.searchParams.set('next', pathname);
        return NextResponse.redirect(url);
      }
    }

    // ── Recycler dashboard guard ─────────────────────────────────────────────────
    if (pathname.startsWith('/recycler/dashboard')) {
      if (!user) {
        const url = request.nextUrl.clone();
        url.pathname = '/recycler/login';
        url.searchParams.set('next', pathname);
        return NextResponse.redirect(url);
      }
    }

    // ── Admin route guard ────────────────────────────────────────────────────────
    if (pathname.startsWith('/admin')) {
      if (!user) {
        const url = request.nextUrl.clone();
        url.pathname = '/admin/login';
        if (pathname === '/admin/login') return supabaseResponse;
        return NextResponse.redirect(url);
      }

      if (pathname !== '/admin/login') {
        const { data: profile } = await supabase
          .from('profiles')
          .select('role')
          .eq('id', user.id)
          .single();

        if (profile?.role !== 'admin') {
          const url = request.nextUrl.clone();
          url.pathname = '/';
          return NextResponse.redirect(url);
        }
      }
    }
  } catch (err) {
    console.warn('Middleware Supabase auth error:', err);
  }

  return supabaseResponse;
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
};
