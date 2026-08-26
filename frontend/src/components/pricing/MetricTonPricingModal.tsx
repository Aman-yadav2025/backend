'use client';

import React, { useState, useMemo } from 'react';
import Link from 'next/link';
import {
  X,
  Building2,
  Factory,
  CheckCircle,
  Sparkles,
  Zap,
  ShieldCheck,
  ArrowRight,
  TrendingUp,
  SlidersHorizontal,
  Info,
} from 'lucide-react';

interface MetricTonPricingModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type UserRole = 'brand' | 'recycler';

interface PlanTier {
  id: 'starter' | 'growth' | 'enterprise';
  name: string;
  badge?: string;
  minMT: number;
  maxMT: number;
  brandPricePerMT: number;
  recyclerPricePerMT: number;
  description: string;
  features: string[];
}

const PLAN_TIERS: PlanTier[] = [
  {
    id: 'starter',
    name: 'Starter Plan',
    minMT: 10,
    maxMT: 100,
    brandPricePerMT: 450,
    recyclerPricePerMT: 180,
    description: 'Ideal for small brands & local recyclers managing initial CPCB compliance targets.',
    features: [
      'Basic CPCB EPR Credit Ledger',
      'Standard Invoice & Weighbridge verification',
      'Automated PDF compliance exports',
      'Email & Community support',
      'Up to 100 MT annual credit processing',
    ],
  },
  {
    id: 'growth',
    name: 'Growth Plan',
    badge: 'Most Popular',
    minMT: 101,
    maxMT: 1000,
    brandPricePerMT: 350,
    recyclerPricePerMT: 130,
    description: 'Designed for mid-sized manufacturers and high-throughput recycling facilities.',
    features: [
      'Everything in Starter, plus:',
      'Priority marketplace credit matching',
      'Batch weighbridge slip validation',
      'Dedicated compliance manager support',
      'Quarterly CPCB audit readiness reports',
      'Multi-category plastic tracking (Cat I-IV)',
    ],
  },
  {
    id: 'enterprise',
    name: 'Enterprise Plan',
    badge: 'Best Value',
    minMT: 1001,
    maxMT: 50000,
    brandPricePerMT: 250,
    recyclerPricePerMT: 90,
    description: 'Tailored for enterprise brands, multi-plant producers & national recyclers.',
    features: [
      'Everything in Growth, plus:',
      'Direct CPCB portal API automated sync',
      'Custom ERP & ERP/SAP integration',
      '24/7 Priority SLA & Dedicated Account Lead',
      'Custom volume bulk rate discounts',
      'Tamper-evident blockchain ledger audit trail',
    ],
  },
];

const PRESET_VOLUMES = [50, 250, 750, 2500, 10000];

export const MetricTonPricingModal: React.FC<MetricTonPricingModalProps> = ({
  isOpen,
  onClose,
}) => {
  const [role, setRole] = useState<UserRole>('brand');
  const [metricTons, setMetricTons] = useState<number>(250);

  // Determine active plan tier based on selected metric tons
  const activePlan = useMemo(() => {
    if (metricTons <= 100) return PLAN_TIERS[0];
    if (metricTons <= 1000) return PLAN_TIERS[1];
    return PLAN_TIERS[2];
  }, [metricTons]);

  // Calculate pricing metrics
  const pricePerMT = role === 'brand' ? activePlan.brandPricePerMT : activePlan.recyclerPricePerMT;
  const totalAnnualCost = metricTons * pricePerMT;
  const totalMonthlyCost = Math.round(totalAnnualCost / 12);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 overflow-y-auto bg-slate-900/60 backdrop-blur-md transition-all">
      <div
        className="relative w-full max-w-4xl bg-white rounded-3xl shadow-2xl border border-slate-200 overflow-hidden my-8 animate-in fade-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="bg-gradient-to-r from-[#0F172A] via-[#1E293B] to-[#0F766E] text-white p-6 sm:p-8 relative">
          <button
            onClick={onClose}
            className="absolute top-5 right-5 p-2 text-slate-300 hover:text-white bg-white/10 hover:bg-white/20 rounded-full transition-colors"
            aria-label="Close modal"
          >
            <X className="w-5 h-5" />
          </button>

          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#ECFDF5]/10 border border-[#ECFDF5]/20 text-[#ECFDF5] text-xs font-bold mb-3">
            <Sparkles className="w-3.5 h-3.5 text-teal-300" />
            <span>Volume-Based Pricing Calculator</span>
          </div>

          <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
            Explore Price Plans by Metric Tons
          </h2>
          <p className="mt-2 text-xs sm:text-sm text-slate-300 max-w-xl">
            Select your organization type and estimated annual plastic volume in Metric Tons (MT) to find the most cost-effective CPCB EPR compliance plan.
          </p>

          {/* Role Switcher Toggle */}
          <div className="mt-6 inline-flex p-1.5 bg-slate-800/80 rounded-2xl border border-slate-700/80">
            <button
              onClick={() => setRole('brand')}
              className={`flex items-center gap-2 px-4 sm:px-6 py-2.5 rounded-xl font-bold text-xs sm:text-sm transition-all ${
                role === 'brand'
                  ? 'bg-[#0F766E] text-white shadow-md shadow-[#0F766E]/40'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <Building2 className="w-4 h-4" />
              <span>Brand / PIBO (Buyer)</span>
            </button>

            <button
              onClick={() => setRole('recycler')}
              className={`flex items-center gap-2 px-4 sm:px-6 py-2.5 rounded-xl font-bold text-xs sm:text-sm transition-all ${
                role === 'recycler'
                  ? 'bg-[#0F766E] text-white shadow-md shadow-[#0F766E]/40'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <Factory className="w-4 h-4" />
              <span>Recycler / Processor (Seller)</span>
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="p-6 sm:p-8 space-y-8 bg-[#FAFAF8]">
          {/* Metric Ton Interactive Control */}
          <div className="bg-white p-6 rounded-2xl border border-[#D6E8DE] shadow-xs">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
              <div>
                <label className="flex items-center gap-2 font-bold text-[#0F172A] text-sm">
                  <SlidersHorizontal className="w-4 h-4 text-[#0F766E]" />
                  <span>Annual Plastic Volume (Metric Tons)</span>
                </label>
                <p className="text-xs text-slate-500 mt-0.5">
                  Adjust slider or enter annual metric tonnage (MT)
                </p>
              </div>

              <div className="flex items-center gap-2 self-start sm:self-auto">
                <input
                  type="number"
                  min="10"
                  max="50000"
                  value={metricTons}
                  onChange={(e) => setMetricTons(Math.max(10, Number(e.target.value) || 10))}
                  className="w-28 px-3 py-2 border-2 border-[#0F766E]/30 focus:border-[#0F766E] rounded-xl font-extrabold text-[#0F766E] text-right text-base outline-none bg-[#ECFDF5]/30"
                />
                <span className="font-bold text-sm text-slate-600">MT / Year</span>
              </div>
            </div>

            {/* Slider */}
            <input
              type="range"
              min="10"
              max="5000"
              step="10"
              value={metricTons > 5000 ? 5000 : metricTons}
              onChange={(e) => setMetricTons(Number(e.target.value))}
              className="w-full h-3 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-[#0F766E]"
            />

            {/* Presets */}
            <div className="mt-4 flex flex-wrap items-center gap-2 pt-2 border-t border-slate-100">
              <span className="text-xs font-semibold text-slate-500 mr-2">Quick Presets:</span>
              {PRESET_VOLUMES.map((preset) => (
                <button
                  key={preset}
                  onClick={() => setMetricTons(preset)}
                  className={`px-3 py-1 rounded-lg text-xs font-bold transition-all ${
                    metricTons === preset
                      ? 'bg-[#0F766E] text-white shadow-xs'
                      : 'bg-slate-100 hover:bg-slate-200 text-slate-700'
                  }`}
                >
                  {preset.toLocaleString()} MT
                </button>
              ))}
            </div>
          </div>

          {/* Dynamic Plans Display */}
          <div className="grid md:grid-cols-3 gap-4 sm:gap-6">
            {PLAN_TIERS.map((tier) => {
              const isSelected = activePlan.id === tier.id;
              const planPricePerMT = role === 'brand' ? tier.brandPricePerMT : tier.recyclerPricePerMT;
              const planAnnualEst = metricTons * planPricePerMT;

              return (
                <div
                  key={tier.id}
                  onClick={() => {
                    // Adjust slider to tier range if clicked
                    if (metricTons < tier.minMT || metricTons > tier.maxMT) {
                      setMetricTons(tier.minMT);
                    }
                  }}
                  className={`relative p-5 sm:p-6 rounded-2xl border-2 transition-all cursor-pointer flex flex-col justify-between ${
                    isSelected
                      ? 'bg-white border-[#0F766E] shadow-xl ring-2 ring-[#0F766E]/20 scale-[1.02]'
                      : 'bg-white/70 border-slate-200 hover:border-slate-300 opacity-80 hover:opacity-100'
                  }`}
                >
                  {tier.badge && (
                    <div className="absolute -top-3 right-4 bg-gradient-to-r from-[#0F766E] to-teal-600 text-white text-[10px] font-black uppercase px-2.5 py-0.5 rounded-full shadow-xs tracking-wider">
                      {tier.badge}
                    </div>
                  )}

                  <div>
                    <div className="flex items-center justify-between">
                      <h3 className="font-extrabold text-[#0F172A] text-lg">{tier.name}</h3>
                      {isSelected && (
                        <span className="flex items-center gap-1 text-[11px] font-bold text-[#0F766E] bg-[#ECFDF5] px-2 py-0.5 rounded-md border border-[#D6E8DE]">
                          <CheckCircle className="w-3 h-3" /> Recommended
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-500 mt-1 min-h-[36px]">{tier.description}</p>

                    <div className="my-4 p-3 rounded-xl bg-[#FAFAF8] border border-slate-100">
                      <div className="text-2xl font-black text-[#0F766E]">
                        ₹{planPricePerMT}
                        <span className="text-xs font-semibold text-slate-500"> / MT</span>
                      </div>
                      <div className="text-xs font-medium text-slate-600 mt-0.5">
                        Est. ₹{planAnnualEst.toLocaleString('en-IN')}/yr for {metricTons.toLocaleString()} MT
                      </div>
                    </div>

                    <div className="space-y-2 mt-4 text-xs">
                      {tier.features.map((feat, idx) => (
                        <div key={idx} className="flex items-start gap-2 text-slate-700">
                          <CheckCircle className={`w-3.5 h-3.5 shrink-0 mt-0.5 ${isSelected ? 'text-[#16A34A]' : 'text-slate-400'}`} />
                          <span className="font-medium">{feat}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="mt-6 pt-4 border-t border-slate-100">
                    <Link
                      href={role === 'brand' ? `/brand/signup?plan=${tier.id}&mt=${metricTons}` : `/recycler/signup?plan=${tier.id}&mt=${metricTons}`}
                      onClick={onClose}
                      className={`w-full py-2.5 px-4 rounded-xl text-xs font-bold flex items-center justify-center gap-2 transition-all ${
                        isSelected
                          ? 'bg-[#0F766E] text-white hover:bg-[#065F46] shadow-md shadow-[#0F766E]/20'
                          : 'bg-slate-100 hover:bg-slate-200 text-slate-700'
                      }`}
                    >
                      <span>Select {tier.name}</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Estimate Summary Banner */}
          <div className="bg-gradient-to-r from-[#0F766E] to-[#065F46] rounded-2xl p-6 text-white flex flex-col sm:flex-row items-center justify-between gap-6 shadow-lg shadow-[#0F766E]/20">
            <div className="space-y-1 text-center sm:text-left">
              <div className="flex items-center justify-center sm:justify-start gap-2 text-xs font-bold text-teal-200 uppercase tracking-wider">
                <TrendingUp className="w-4 h-4" />
                <span>Estimated Cost Calculation</span>
              </div>
              <div className="text-xl sm:text-2xl font-black">
                ₹{totalAnnualCost.toLocaleString('en-IN')}{' '}
                <span className="text-sm font-semibold text-teal-100">/ Year</span>
                <span className="text-xs font-normal text-teal-200 block sm:inline sm:ml-2">
                  (approx. ₹{totalMonthlyCost.toLocaleString('en-IN')}/month)
                </span>
              </div>
              <p className="text-xs text-teal-100">
                Based on <span className="font-bold underline">{metricTons.toLocaleString()} MT</span> annual volume as a{' '}
                <span className="font-bold capitalize">{role === 'brand' ? 'Brand / PIBO' : 'Recycler / Processor'}</span> under the{' '}
                <span className="font-bold">{activePlan.name}</span> (₹{pricePerMT}/MT).
              </p>
            </div>

            <div className="flex flex-col sm:flex-row items-center gap-3 w-full sm:w-auto">
              <Link
                href={role === 'brand' ? `/brand/signup?plan=${activePlan.id}&mt=${metricTons}` : `/recycler/signup?plan=${activePlan.id}&mt=${metricTons}`}
                onClick={onClose}
                className="w-full sm:w-auto px-6 py-3 bg-white text-[#0F766E] font-extrabold text-xs sm:text-sm rounded-xl shadow-md hover:bg-emerald-50 transition-all text-center flex items-center justify-center gap-2"
              >
                <span>Proceed to {role === 'brand' ? 'Brand' : 'Recycler'} Registration</span>
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </div>

          <div className="flex items-center gap-2 text-[11px] text-slate-500 justify-center">
            <Info className="w-3.5 h-3.5 text-slate-400 shrink-0" />
            <span>
              Prices exclude GST. CPCB registration and EPR credit fees subject to actual verified recycling certificate rates.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
