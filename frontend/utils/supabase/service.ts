import { createClient } from '@supabase/supabase-js';

/**
 * Service-role Supabase client.
 * Bypasses RLS — use only in server-side API routes, never in the browser.
 * Requires SUPABASE_SERVICE_ROLE_KEY (set in .env.local, never NEXT_PUBLIC_).
 */
export const createServiceClient = () =>
  createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!,
  );
