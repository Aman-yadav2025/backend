'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowLeft, Tag, Loader2, Check, RefreshCw, Info } from 'lucide-react';

const PLANS = ['starter', 'growth', 'enterprise'];
const TIERS = ['tier1', 'tier2', 'tier3'];
const ROLES = ['brand', 'recycler'];

function generateCode(): string {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  let s = '';
  for (let i = 0; i < 5; i++) s += chars[Math.floor(Math.random() * chars.length)];
  return `PNVR-${s}`;
}

export function AdminCreatePromoView() {
  const router = useRouter();

  // Form state
  const [code, setCode] = useState('');
  const [discountType, setDiscountType] = useState<'percentage' | 'flat'>('percentage');
  const [discountValue, setDiscountValue] = useState('');
  const [description, setDescription] = useState('');
  const [maxUses, setMaxUses] = useState('');
  const [validFrom, setValidFrom] = useState(new Date().toISOString().slice(0, 16));
  const [validUntil, setValidUntil] = useState('');
  const [selectedPlans, setSelectedPlans] = useState<string[]>([]);
  const [selectedTiers, setSelectedTiers] = useState<string[]>([]);
  const [selectedRoles, setSelectedRoles] = useState<string[]>([]);

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdCode, setCreatedCode] = useState<string | null>(null);

  const togglePlan = (p: string) =>
    setSelectedPlans((prev) => prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]);

  const toggleTier = (t: string) =>
    setSelectedTiers((prev) => prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]);

  const toggleRole = (r: string) =>
    setSelectedRoles((prev) => prev.includes(r) ? prev.filter((x) => x !== r) : [...prev, r]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const numValue = Number(discountValue);
    if (!numValue || numValue <= 0) {
      setError('Discount value must be a positive number.');
      return;
    }
    if (discountType === 'percentage' && numValue > 100) {
      setError('Percentage discount cannot exceed 100.');
      return;
    }

    setIsLoading(true);
    try {
      // For flat, user enters INR — convert to paise internally
      const payloadValue = discountType === 'flat' ? Math.round(numValue * 100) : numValue;

      const res = await fetch('/api/admin/promo/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code: code.trim() || undefined,
          discountType,
          discountValue: payloadValue,
          description: description.trim() || undefined,
          maxUses: maxUses ? Number(maxUses) : null,
          validFrom: new Date(validFrom).toISOString(),
          validUntil: validUntil ? new Date(validUntil).toISOString() : null,
          applicablePlans: selectedPlans,
          applicableTiers: selectedTiers,
          applicableRoles: selectedRoles,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        setError(data.error || 'Failed to create promo code.');
        return;
      }

      setCreatedCode(data.promo.code);
    } catch {
      setError('Network error. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  // ── Success state ────────────────────────────────────────────────────────────
  if (createdCode) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-3xl p-8 max-w-md w-full border border-slate-200 shadow-xl text-center">
          <div className="w-14 h-14 rounded-2xl bg-[#0F766E] text-white flex items-center justify-center mx-auto mb-5 shadow-lg shadow-[#0F766E]/30">
            <Check className="w-8 h-8" />
          </div>
          <h2 className="text-xl font-black text-slate-900 mb-2">Promo Code Created</h2>
          <p className="text-sm text-slate-500 mb-5">Share this code with your users:</p>
          <div className="bg-slate-50 border border-slate-200 rounded-2xl p-4 mb-6">
            <span className="font-mono text-2xl font-black text-[#0F766E] tracking-widest">
              {createdCode}
            </span>
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => {
                setCreatedCode(null);
                setCode('');
                setDiscountValue('');
                setDescription('');
                setMaxUses('');
                setValidUntil('');
                setSelectedPlans([]);
                setSelectedTiers([]);
                setSelectedRoles([]);
              }}
              className="flex-1 py-3 rounded-xl border border-slate-200 text-sm font-bold text-slate-700 hover:bg-slate-50 cursor-pointer transition-colors flex items-center justify-center gap-2"
            >
              <RefreshCw className="w-4 h-4" />
              Create Another
            </button>
            <Link
              href="/admin/promo"
              className="flex-1 py-3 rounded-xl bg-[#0F766E] text-white text-sm font-bold hover:bg-[#065F46] transition-colors flex items-center justify-center gap-2"
            >
              <Tag className="w-4 h-4" />
              View All Codes
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // ── Form ─────────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-2xl mx-auto px-4 sm:px-6 h-16 flex items-center gap-3">
          <Link
            href="/admin/promo"
            className="p-2 rounded-lg text-slate-500 hover:bg-slate-100 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <span className="text-sm font-black text-slate-900">New Promo Code</span>
            <span className="text-xs text-slate-400 block leading-none">Punarvritt Admin</span>
          </div>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 sm:px-6 py-8">
        <form onSubmit={handleSubmit} className="space-y-6">

          {/* Code */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#0F766E]">Code</h3>
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1.5">
                Promo Code <span className="font-normal text-slate-400">(leave blank to auto-generate)</span>
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={code}
                  onChange={(e) => setCode(e.target.value.toUpperCase())}
                  placeholder="e.g. LAUNCH50"
                  maxLength={20}
                  className="flex-1 h-11 px-4 text-sm font-mono font-bold tracking-wider rounded-xl border border-slate-200 bg-slate-50 outline-none focus:border-[#0F766E] focus:bg-white transition-colors text-slate-800 uppercase placeholder:font-sans placeholder:font-normal placeholder:tracking-normal"
                />
                <button
                  type="button"
                  onClick={() => setCode(generateCode())}
                  className="h-11 px-4 rounded-xl border border-slate-200 text-xs font-bold text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer whitespace-nowrap"
                >
                  Generate
                </button>
              </div>
            </div>
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1.5">
                Description <span className="font-normal text-slate-400">(internal note)</span>
              </label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="e.g. Launch discount for early adopters"
                className="w-full h-11 px-4 text-sm rounded-xl border border-slate-200 bg-slate-50 outline-none focus:border-[#0F766E] focus:bg-white transition-colors text-slate-800"
              />
            </div>
          </div>

          {/* Discount */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#0F766E]">Discount</h3>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-2">Discount Type</label>
              <div className="flex gap-3">
                {(['percentage', 'flat'] as const).map((type) => (
                  <button
                    key={type}
                    type="button"
                    onClick={() => setDiscountType(type)}
                    className={`flex-1 py-2.5 rounded-xl text-sm font-bold border transition-all cursor-pointer ${
                      discountType === type
                        ? 'bg-[#0F766E] text-white border-[#0F766E]'
                        : 'bg-slate-50 text-slate-600 border-slate-200 hover:border-[#0F766E]/40'
                    }`}
                  >
                    {type === 'percentage' ? '% Percentage' : '₹ Flat Amount'}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1.5">
                {discountType === 'percentage' ? 'Discount Percentage (1–100)' : 'Discount Amount (₹ in rupees)'}
              </label>
              <div className="relative">
                <span className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 text-sm font-bold pointer-events-none">
                  {discountType === 'percentage' ? '%' : '₹'}
                </span>
                <input
                  type="number"
                  value={discountValue}
                  onChange={(e) => setDiscountValue(e.target.value)}
                  placeholder={discountType === 'percentage' ? '20' : '5000'}
                  required
                  min={1}
                  max={discountType === 'percentage' ? 100 : undefined}
                  className="w-full h-11 pl-9 pr-4 text-sm rounded-xl border border-slate-200 bg-slate-50 outline-none focus:border-[#0F766E] focus:bg-white transition-colors text-slate-800"
                />
              </div>
              {discountType === 'flat' && (
                <p className="text-[11px] text-slate-400 mt-1 flex items-center gap-1">
                  <Info className="w-3 h-3" />
                  Enter amount in rupees (e.g. 5000 for ₹5,000 off)
                </p>
              )}
            </div>
          </div>

          {/* Restrictions */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#0F766E]">
              Restrictions <span className="font-normal text-slate-400 normal-case">(leave empty = applies to all)</span>
            </h3>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-2">Applicable Roles</label>
              <div className="flex gap-2 flex-wrap">
                {ROLES.map((r) => (
                  <button
                    key={r}
                    type="button"
                    onClick={() => toggleRole(r)}
                    className={`px-4 py-2 rounded-xl text-xs font-bold border transition-all cursor-pointer capitalize ${
                      selectedRoles.includes(r)
                        ? 'bg-[#0F766E] text-white border-[#0F766E]'
                        : 'bg-slate-50 text-slate-600 border-slate-200 hover:border-[#0F766E]/40'
                    }`}
                  >
                    {r}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-2">Applicable Plans</label>
              <div className="flex gap-2 flex-wrap">
                {PLANS.map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => togglePlan(p)}
                    className={`px-4 py-2 rounded-xl text-xs font-bold border transition-all cursor-pointer capitalize ${
                      selectedPlans.includes(p)
                        ? 'bg-[#0F766E] text-white border-[#0F766E]'
                        : 'bg-slate-50 text-slate-600 border-slate-200 hover:border-[#0F766E]/40'
                    }`}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-2">Applicable Tiers</label>
              <div className="flex gap-2 flex-wrap">
                {TIERS.map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => toggleTier(t)}
                    className={`px-4 py-2 rounded-xl text-xs font-bold border transition-all cursor-pointer uppercase ${
                      selectedTiers.includes(t)
                        ? 'bg-[#0F766E] text-white border-[#0F766E]'
                        : 'bg-slate-50 text-slate-600 border-slate-200 hover:border-[#0F766E]/40'
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Limits */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#0F766E]">Usage & Validity</h3>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1.5">
                Max Uses <span className="font-normal text-slate-400">(leave blank = unlimited)</span>
              </label>
              <input
                type="number"
                value={maxUses}
                onChange={(e) => setMaxUses(e.target.value)}
                placeholder="100"
                min={1}
                className="w-full h-11 px-4 text-sm rounded-xl border border-slate-200 bg-slate-50 outline-none focus:border-[#0F766E] focus:bg-white transition-colors text-slate-800"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1.5">Valid From</label>
                <input
                  type="datetime-local"
                  value={validFrom}
                  onChange={(e) => setValidFrom(e.target.value)}
                  required
                  className="w-full h-11 px-4 text-sm rounded-xl border border-slate-200 bg-slate-50 outline-none focus:border-[#0F766E] focus:bg-white transition-colors text-slate-800"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1.5">
                  Valid Until <span className="font-normal text-slate-400">(optional)</span>
                </label>
                <input
                  type="datetime-local"
                  value={validUntil}
                  onChange={(e) => setValidUntil(e.target.value)}
                  className="w-full h-11 px-4 text-sm rounded-xl border border-slate-200 bg-slate-50 outline-none focus:border-[#0F766E] focus:bg-white transition-colors text-slate-800"
                />
              </div>
            </div>
          </div>

          {error && (
            <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs font-semibold">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={isLoading || !discountValue}
            className="w-full h-12 rounded-xl bg-[#0F766E] text-white font-bold text-sm flex items-center justify-center gap-2 hover:bg-[#065F46] disabled:opacity-60 disabled:cursor-not-allowed transition-colors cursor-pointer"
          >
            {isLoading
              ? <><Loader2 className="w-5 h-5 animate-spin" /> Creating…</>
              : <><Tag className="w-5 h-5" /> Create Promo Code</>
            }
          </button>
        </form>
      </main>
    </div>
  );
}
