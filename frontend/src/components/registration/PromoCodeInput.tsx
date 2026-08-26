'use client';

import React, { useState } from 'react';
import { Tag, CheckCircle2, XCircle, Loader2, X } from 'lucide-react';
import type { CapacityTier, SubscriptionPlanId } from '../../types/registration';
import type { ValidatePromoResponse } from '../../app/api/promo/validate/route';

interface PromoCodeInputProps {
  capacityTier: CapacityTier;
  subscriptionPlan: SubscriptionPlanId;
  registrationType: 'brand' | 'recycler';
  appliedCode: string | null;
  discountAmount: number;        // paise
  onApply: (code: string, discountAmount: number, finalAmount: number, originalAmount: number) => void;
  onRemove: () => void;
}

function formatPaise(paise: number): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(paise / 100);
}

export const PromoCodeInput: React.FC<PromoCodeInputProps> = ({
  capacityTier,
  subscriptionPlan,
  registrationType,
  appliedCode,
  discountAmount,
  onApply,
  onRemove,
}) => {
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleApply = async () => {
    if (!inputValue.trim()) return;
    setError(null);
    setIsLoading(true);

    try {
      const res = await fetch('/api/promo/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code: inputValue.trim().toUpperCase(),
          capacityTier,
          subscriptionPlan,
          registrationType,
        }),
      });

      const data: ValidatePromoResponse = await res.json();

      if (!data.valid) {
        setError(data.error ?? 'Invalid promo code.');
      } else {
        onApply(
          inputValue.trim().toUpperCase(),
          data.discountAmount!,
          data.finalAmount!,
          data.originalAmount!,
        );
        setInputValue('');
        setError(null);
      }
    } catch {
      setError('Could not validate code. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleApply();
    }
  };

  // ── Applied state ────────────────────────────────────────────────────────────
  if (appliedCode) {
    return (
      <div className="bg-[#ECFDF5] border border-[#6EE7B7] rounded-2xl p-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-[#0F766E] text-white flex items-center justify-center shrink-0">
              <CheckCircle2 className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs font-bold text-[#0F172A]">
                Promo code applied
              </p>
              <p className="text-[11px] text-slate-500">
                <span className="font-mono font-bold text-[#0F766E] tracking-wider">{appliedCode}</span>
                {' '}— you save{' '}
                <span className="font-bold text-[#16A34A]">{formatPaise(discountAmount)}</span>
              </p>
            </div>
          </div>
          <button
            onClick={onRemove}
            className="p-1.5 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors cursor-pointer"
            title="Remove promo code"
            type="button"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>
    );
  }

  // ── Input state ──────────────────────────────────────────────────────────────
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Tag className="w-4 h-4 text-[#0F766E] shrink-0" />
        <span className="text-xs font-bold text-[#0F172A]">Have a promo code?</span>
      </div>

      <div className="flex gap-2">
        <div className="relative flex-1">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => {
              setInputValue(e.target.value.toUpperCase());
              if (error) setError(null);
            }}
            onKeyDown={handleKeyDown}
            placeholder="Enter code e.g. PNVR-A3KX9"
            maxLength={20}
            className={`w-full h-11 px-4 text-sm font-mono font-bold tracking-wider rounded-xl border bg-white outline-none transition-colors placeholder:font-sans placeholder:font-normal placeholder:tracking-normal placeholder:text-slate-400 ${
              error
                ? 'border-red-300 focus:border-red-400 text-red-700'
                : 'border-[#D6E8DE] focus:border-[#0F766E] text-[#0F172A]'
            }`}
          />
        </div>
        <button
          onClick={handleApply}
          disabled={isLoading || !inputValue.trim()}
          type="button"
          className="h-11 px-5 rounded-xl bg-[#0F766E] text-white text-sm font-bold transition-all hover:bg-[#065F46] disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 shrink-0 cursor-pointer"
        >
          {isLoading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            'Apply'
          )}
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-xs text-red-600 font-semibold">
          <XCircle className="w-3.5 h-3.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
};
