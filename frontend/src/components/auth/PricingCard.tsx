'use client';

import React from 'react';
import { Check, Sparkles } from 'lucide-react';
import { Button } from '../ui/Button';

export interface Plan {
  id: string;
  name: string;
  price: string;
  period?: string;
  description: string;
  features: string[];
  popular?: boolean;
  badge?: string;
}

interface PricingCardProps {
  plan: Plan;
  isSelected: boolean;
  onSelect: (planId: string) => void;
}

export const PricingCard: React.FC<PricingCardProps> = ({
  plan,
  isSelected,
  onSelect,
}) => {
  return (
    <div
      onClick={() => onSelect(plan.id)}
      className={`
        relative rounded-2xl p-6 sm:p-7 bg-white border-2 transition-all duration-200 cursor-pointer flex flex-col justify-between
        ${
          isSelected
            ? 'border-emerald-600 ring-4 ring-emerald-500/15 shadow-lg bg-emerald-50/10'
            : 'border-slate-200 hover:border-slate-300 hover:shadow-md'
        }
      `}
    >
      {plan.popular && (
        <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 bg-emerald-600 text-white text-[11px] font-bold tracking-wider uppercase px-3 py-0.5 rounded-full shadow-sm flex items-center gap-1">
          <Sparkles className="w-3 h-3" />
          <span>Most Popular</span>
        </div>
      )}

      <div>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-xl font-bold text-slate-900">{plan.name}</h3>
          {isSelected && (
            <div className="w-6 h-6 rounded-full bg-emerald-600 text-white flex items-center justify-center">
              <Check className="w-4 h-4 stroke-[3]" />
            </div>
          )}
        </div>

        <p className="text-xs text-slate-500 min-h-[36px] mb-4">
          {plan.description}
        </p>

        <div className="mb-6 pb-6 border-b border-slate-100 flex items-baseline gap-1">
          <span className="text-3xl font-extrabold text-slate-900">{plan.price}</span>
          {plan.period && <span className="text-xs font-semibold text-slate-500">{plan.period}</span>}
        </div>

        <ul className="space-y-3 mb-6">
          {plan.features.map((feature, index) => (
            <li key={index} className="flex items-start gap-2.5 text-xs text-slate-700 font-medium leading-tight">
              <div className="w-4 h-4 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center shrink-0 mt-0.5">
                <Check className="w-3 h-3 stroke-[3]" />
              </div>
              <span>{feature}</span>
            </li>
          ))}
        </ul>
      </div>

      <Button
        variant={isSelected ? 'primary' : 'outline'}
        fullWidth
        size="md"
        onClick={(e) => {
          e.stopPropagation();
          onSelect(plan.id);
        }}
      >
        {isSelected ? 'Plan Selected' : 'Select Plan'}
      </Button>
    </div>
  );
};
