'use client';

import React, { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Plus,
  Tag,
  ToggleLeft,
  ToggleRight,
  Copy,
  Check,
  RefreshCw,
  LogOut,
  ChevronRight,
  Percent,
  IndianRupee,
} from 'lucide-react';
import { createClient } from '@/utils/supabase/client';

interface PromoCode {
  id: string;
  code: string;
  discount_type: 'percentage' | 'flat';
  discount_value: number;
  description: string | null;
  max_uses: number | null;
  current_uses: number;
  valid_from: string;
  valid_until: string | null;
  is_active: boolean;
  applicable_plans: string[] | null;
  applicable_tiers: string[] | null;
  applicable_roles: string[] | null;
  created_at: string;
}

function formatPaise(paise: number): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency', currency: 'INR', maximumFractionDigits: 0,
  }).format(paise / 100);
}

export function AdminPromoListView() {
  const router = useRouter();
  const [promos, setPromos] = useState<PromoCode[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  const fetchPromos = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/admin/promo/list');
      const data = await res.json();
      if (!res.ok) { setError(data.error || 'Failed to load promo codes.'); return; }
      setPromos(data.promos);
    } catch {
      setError('Network error. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { fetchPromos(); }, [fetchPromos]);

  const handleSignOut = async () => {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push('/admin/login');
  };

  const copyCode = (code: string, id: string) => {
    navigator.clipboard.writeText(code);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1500);
  };

  const toggleActive = async (id: string, current: boolean) => {
    setTogglingId(id);
    try {
      await fetch('/api/admin/promo/list', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, is_active: !current }),
      });
      setPromos((prev) => prev.map((p) => p.id === id ? { ...p, is_active: !current } : p));
    } finally {
      setTogglingId(null);
    }
  };

  const isExpired = (p: PromoCode) =>
    !!p.valid_until && new Date(p.valid_until) < new Date();
  const isMaxed = (p: PromoCode) =>
    p.max_uses !== null && p.current_uses >= p.max_uses;

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Top nav */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[#0F766E] text-white flex items-center justify-center">
              <Tag className="w-4 h-4" />
            </div>
            <div>
              <span className="text-sm font-black text-slate-900">Punarvritt Admin</span>
              <span className="text-xs text-slate-400 block leading-none">Promo Codes</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={fetchPromos}
              className="p-2 rounded-lg text-slate-500 hover:bg-slate-100 transition-colors cursor-pointer"
              title="Refresh"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
            <Link
              href="/admin/promo/new"
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-[#0F766E] text-white text-sm font-bold hover:bg-[#065F46] transition-colors"
            >
              <Plus className="w-4 h-4" />
              <span>New Code</span>
            </Link>
            <button
              onClick={handleSignOut}
              className="p-2 rounded-lg text-slate-500 hover:bg-red-50 hover:text-red-500 transition-colors cursor-pointer"
              title="Sign out"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 sm:px-6 py-8">
        {/* Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
          {[
            { label: 'Total Codes', value: promos.length },
            { label: 'Active', value: promos.filter((p) => p.is_active && !isExpired(p) && !isMaxed(p)).length },
            { label: 'Total Uses', value: promos.reduce((s, p) => s + p.current_uses, 0) },
            { label: 'Expired / Maxed', value: promos.filter((p) => isExpired(p) || isMaxed(p)).length },
          ].map((stat) => (
            <div key={stat.label} className="bg-white rounded-2xl border border-slate-200 p-4">
              <p className="text-2xl font-black text-slate-900">{stat.value}</p>
              <p className="text-xs text-slate-500 mt-0.5">{stat.label}</p>
            </div>
          ))}
        </div>

        {/* Table */}
        <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-800">All Promo Codes</h2>
            <span className="text-xs text-slate-400">{promos.length} codes</span>
          </div>

          {isLoading ? (
            <div className="flex items-center justify-center py-16 text-slate-400">
              <RefreshCw className="w-5 h-5 animate-spin mr-2" />
              <span className="text-sm">Loading…</span>
            </div>
          ) : error ? (
            <div className="text-center py-16 text-red-500 text-sm">{error}</div>
          ) : promos.length === 0 ? (
            <div className="text-center py-16 text-slate-400">
              <Tag className="w-10 h-10 mx-auto mb-3 opacity-30" />
              <p className="text-sm font-medium">No promo codes yet.</p>
              <Link href="/admin/promo/new" className="text-[#0F766E] font-bold text-sm mt-2 inline-flex items-center gap-1 hover:underline">
                Create your first one <ChevronRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {promos.map((promo) => {
                const expired = isExpired(promo);
                const maxed = isMaxed(promo);
                const statusLabel = !promo.is_active ? 'Disabled' : expired ? 'Expired' : maxed ? 'Maxed' : 'Active';
                const statusColor = !promo.is_active ? 'bg-slate-100 text-slate-500' : expired ? 'bg-amber-100 text-amber-700' : maxed ? 'bg-orange-100 text-orange-700' : 'bg-[#ECFDF5] text-[#16A34A]';

                return (
                  <div key={promo.id} className="px-6 py-4 flex items-start gap-4 hover:bg-slate-50 transition-colors">
                    {/* Discount icon */}
                    <div className="w-9 h-9 rounded-xl bg-slate-100 flex items-center justify-center shrink-0 mt-0.5">
                      {promo.discount_type === 'percentage'
                        ? <Percent className="w-4 h-4 text-[#0F766E]" />
                        : <IndianRupee className="w-4 h-4 text-[#0F766E]" />
                      }
                    </div>

                    {/* Code + details */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className="font-mono font-bold text-sm text-slate-900 tracking-wider">{promo.code}</span>
                        <button
                          onClick={() => copyCode(promo.code, promo.id)}
                          className="text-slate-400 hover:text-[#0F766E] cursor-pointer"
                          title="Copy code"
                        >
                          {copiedId === promo.id
                            ? <Check className="w-3.5 h-3.5 text-[#16A34A]" />
                            : <Copy className="w-3.5 h-3.5" />
                          }
                        </button>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${statusColor}`}>
                          {statusLabel}
                        </span>
                      </div>
                      <p className="text-xs text-slate-600 mb-1.5">
                        <span className="font-bold text-[#0F766E]">
                          {promo.discount_type === 'percentage'
                            ? `${promo.discount_value}% off`
                            : `${formatPaise(promo.discount_value)} off`
                          }
                        </span>
                        {promo.description && <span className="text-slate-400"> — {promo.description}</span>}
                      </p>
                      <div className="flex items-center gap-4 text-[10px] text-slate-400 flex-wrap">
                        <span>Uses: <b className="text-slate-600">{promo.current_uses}{promo.max_uses ? `/${promo.max_uses}` : ''}</b></span>
                        {promo.valid_until && (
                          <span>Expires: <b className="text-slate-600">{new Date(promo.valid_until).toLocaleDateString('en-IN')}</b></span>
                        )}
                        {promo.applicable_plans?.length ? (
                          <span>Plans: <b className="text-slate-600">{promo.applicable_plans.join(', ')}</b></span>
                        ) : null}
                        {promo.applicable_tiers?.length ? (
                          <span>Tiers: <b className="text-slate-600">{promo.applicable_tiers.join(', ')}</b></span>
                        ) : null}
                        {promo.applicable_roles?.length ? (
                          <span>Roles: <b className="text-slate-600 capitalize">{promo.applicable_roles.join(', ')}</b></span>
                        ) : null}
                      </div>
                    </div>

                    {/* Toggle active */}
                    <button
                      onClick={() => toggleActive(promo.id, promo.is_active)}
                      disabled={togglingId === promo.id}
                      className="shrink-0 cursor-pointer disabled:opacity-50"
                      title={promo.is_active ? 'Disable code' : 'Enable code'}
                    >
                      {promo.is_active
                        ? <ToggleRight className="w-7 h-7 text-[#0F766E]" />
                        : <ToggleLeft className="w-7 h-7 text-slate-300" />
                      }
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
