'use client';

import React from 'react';
import { motion } from 'motion/react';
import { Check, Sparkles, ArrowRight, CheckCircle2 } from 'lucide-react';
import { CapacityTier, SubscriptionPlanId } from '../../types/registration';
import { PLAN_DETAILS, PRICING_MATRIX } from '../../data/pricing';
import { AnimatedBadge } from './AnimatedBadge';

interface PricingCardProps {
  capacityTier: CapacityTier;
  selectedPlan: SubscriptionPlanId;
  onSelectPlan: (plan: SubscriptionPlanId) => void;
}

export const PricingCard: React.FC<PricingCardProps> = ({
  capacityTier,
  selectedPlan,
  onSelectPlan,
}) => {
  const tierPricing = PRICING_MATRIX[capacityTier];

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 sm:gap-8 items-stretch">
      {PLAN_DETAILS.map((plan) => {
        const isSelected = selectedPlan === plan.id;
        const priceInfo =
          tierPricing[plan.id] || { price: 'Custom', period: 'Contact Sales' };

        return (
          <motion.div
            key={plan.id}
            whileHover={{ y: -6 }}
            whileTap={{ scale: 0.99 }}
            animate={{
              scale: isSelected ? 1.02 : 1,
              borderColor: isSelected ? '#0F766E' : '#D6E8DE',
            }}
            onClick={() => onSelectPlan(plan.id)}
            className={`relative rounded-3xl p-6 sm:p-8 border-2 flex flex-col justify-between transition-all duration-300 cursor-pointer ${
              plan.popular && !isSelected
                ? 'bg-gradient-to-b from-[#ECFDF5]/50 to-white border-emerald-300 shadow-md'
                : isSelected
                ? 'bg-gradient-to-b from-[#ECFDF5]/90 via-white to-white border-[#0F766E] shadow-xl shadow-[#0F766E]/20 ring-2 ring-[#0F766E]/30'
                : 'bg-white border-[#D6E8DE] shadow-xs hover:shadow-lg hover:border-[#0F766E]/40'
            }`}
          >
            {/* Top Badge */}
            {plan.popular && (
              <div className="absolute -top-3.5 left-1/2 -translate-x-1/2">
                <AnimatedBadge variant="popular">MOST CHOSEN</AnimatedBadge>
              </div>
            )}

            <div>
              {/* Header */}
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-xl font-black text-[#0F172A] tracking-tight">
                  {plan.name}
                </h3>
                {isSelected && (
                  <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-[#0F766E] text-white flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Selected</span>
                  </span>
                )}
              </div>

              <p className="text-xs text-slate-500 leading-relaxed mb-6">
                {plan.tagline}
              </p>

              {/* Price Banner */}
              <div className="mb-6 p-4 rounded-2xl bg-[#FAFAF8] border border-[#D6E8DE]">
                <div className="flex items-baseline gap-1">
                  <span className="text-2xl sm:text-3xl font-black text-[#0F172A] tracking-tight">
                    {priceInfo.price}
                  </span>
                  {priceInfo.period !== 'Contact Sales' && (
                    <span className="text-xs font-semibold text-slate-500">
                      /{priceInfo.period}
                    </span>
                  )}
                </div>
                <span className="text-[10px] font-bold text-[#0F766E] block mt-1">
                  Billed annually for {capacityTier.toUpperCase()} capacity
                </span>
              </div>

              {/* Features List */}
              <div className="space-y-3 mb-8">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block mb-2">
                  Plan Features Included:
                </span>
                {plan.features.map((feature, idx) => (
                  <div key={idx} className="flex items-start gap-2.5 text-xs text-[#0F172A] font-medium">
                    <div className="w-4 h-4 rounded-full bg-[#ECFDF5] text-[#16A34A] flex items-center justify-center shrink-0 mt-0.5">
                      <Check className="w-3 h-3 text-[#16A34A] stroke-[3]" />
                    </div>
                    <span>{feature}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Select Button */}
            <button
              onClick={(e) => {
                e.stopPropagation();
                onSelectPlan(plan.id);
              }}
              className={`w-full py-3.5 px-6 rounded-xl font-bold text-sm transition-all duration-200 flex items-center justify-center gap-2 cursor-pointer ${
                isSelected
                  ? 'bg-[#0F766E] text-white shadow-md shadow-[#0F766E]/30 hover:bg-[#065F46]'
                  : 'bg-[#FAFAF8] text-[#0F172A] border border-[#D6E8DE] hover:bg-[#ECFDF5] hover:border-[#0F766E]/50'
              }`}
            >
              <span>{isSelected ? 'Selected Plan' : `Choose ${plan.name}`}</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </motion.div>
        );
      })}
    </div>
  );
};
