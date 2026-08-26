'use client';

import React from 'react';
import { motion } from 'motion/react';
import { Building2, Factory, CheckCircle2, ArrowRight } from 'lucide-react';
import { BrandSubRole, RegistrationType } from '../../types/registration';
import { UserCheck, Shield } from 'lucide-react';

interface RegistrationCardProps {
  type: RegistrationType;
  selected: boolean;
  onSelect: (type: RegistrationType) => void;
  onContinue: () => void;
  brandSubRole?: BrandSubRole;
  onSelectBrandSubRole?: (role: BrandSubRole) => void;
}

export const RegistrationCard: React.FC<RegistrationCardProps> = ({
  type,
  selected,
  onSelect,
  onContinue,
  brandSubRole = 'brand_admin',
  onSelectBrandSubRole,
}) => {
  const isBrand = type === 'brand';

  const title = isBrand ? 'Join as Brand' : 'Join as Recycler';
  const subtitle = isBrand
    ? 'For Brand Owners, Producers & Importers (PIBOs)'
    : 'For Plastic Recyclers, Processors & Aggregators';

  const description = isBrand
    ? 'Register your company to purchase recycled materials, manage EPR compliance, track documentation, and connect with verified recyclers.'
    : 'Register your recycling company, sell recycled materials, manage inventory, upload compliance certificates, and connect with brands.';

  const benefits = isBrand
    ? [
        'Buy recycled plastic',
        'Compliance Dashboard',
        'Invoice Management',
        'Audit Reports',
      ]
    : [
        'Sell materials',
        'Marketplace Access',
        'Buyer Matching',
        'Business Growth',
      ];

  const Icon = isBrand ? Building2 : Factory;

  return (
    <motion.div
      whileHover={{ y: -4 }}
      whileTap={{ scale: 0.99 }}
      animate={{
        scale: selected ? 1.02 : 1,
        borderColor: selected ? '#0F766E' : '#D6E8DE',
      }}
      onClick={() => onSelect(type)}
      className={`relative p-6 sm:p-8 rounded-2xl sm:rounded-3xl border-2 transition-all duration-300 cursor-pointer flex flex-col justify-between ${
        selected
          ? 'bg-gradient-to-b from-[#ECFDF5]/80 via-white to-white border-[#0F766E] shadow-xl shadow-[#0F766E]/15 ring-2 ring-[#0F766E]/20'
          : 'bg-white border-[#D6E8DE] shadow-sm hover:shadow-md hover:border-[#0F766E]/50'
      }`}
    >
      {/* Selected Badge */}
      {selected && (
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          className="absolute top-4 right-4 w-7 h-7 rounded-full bg-[#0F766E] text-white flex items-center justify-center shadow-md"
        >
          <CheckCircle2 className="w-5 h-5" />
        </motion.div>
      )}

      <div>
        {/* Header Icon Graphic */}
        <div className="flex items-center gap-4 mb-5">
          <div
            className={`w-14 h-14 rounded-2xl flex items-center justify-center transition-colors ${
              selected
                ? 'bg-[#0F766E] text-white shadow-md shadow-[#0F766E]/30'
                : 'bg-[#ECFDF5] text-[#0F766E]'
            }`}
          >
            <Icon className="w-7 h-7" />
          </div>
          <div>
            <h3 className="text-xl sm:text-2xl font-black text-[#0F172A] tracking-tight">
              {title}
            </h3>
            <span className="text-xs font-semibold text-[#0F766E] block mt-0.5">
              {subtitle}
            </span>
          </div>
        </div>

        {/* Description */}
        <p className="text-sm text-slate-600 leading-relaxed mb-6 font-normal">
          {description}
        </p>

        {/* Sub-Role Selector for Brand */}
        {isBrand && (
          <div className="border-t border-[#D6E8DE] pt-4 mb-6">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500 block mb-2.5">
              Select Your Brand Role
            </span>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onSelect('brand');
                  if (onSelectBrandSubRole) onSelectBrandSubRole('brand_admin');
                }}
                className={`py-2 px-3 rounded-xl border text-xs font-bold transition-all flex items-center justify-center gap-1.5 cursor-pointer ${
                  brandSubRole === 'brand_admin'
                    ? 'bg-[#0F766E] text-white border-[#0F766E] shadow-xs'
                    : 'bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100'
                }`}
              >
                <Shield className="w-3.5 h-3.5" />
                <span>Brand Admin</span>
              </button>

              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onSelect('brand');
                  if (onSelectBrandSubRole) onSelectBrandSubRole('brand_employee');
                }}
                className={`py-2 px-3 rounded-xl border text-xs font-bold transition-all flex items-center justify-center gap-1.5 cursor-pointer ${
                  brandSubRole === 'brand_employee'
                    ? 'bg-[#0F766E] text-white border-[#0F766E] shadow-xs'
                    : 'bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100'
                }`}
              >
                <UserCheck className="w-3.5 h-3.5" />
                <span>Brand Employee</span>
              </button>
            </div>
          </div>
        )}

        {/* Benefits List */}
        <div className="border-t border-[#D6E8DE] pt-5 mb-8">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400 block mb-3">
            Key Platform Benefits
          </span>
          <div className="grid grid-cols-2 gap-2.5">
            {benefits.map((b, i) => (
              <div key={i} className="flex items-center gap-2 text-xs font-bold text-[#0F172A]">
                <div className="w-4 h-4 rounded-full bg-[#ECFDF5] text-[#0F766E] flex items-center justify-center shrink-0">
                  <CheckCircle2 className="w-3.5 h-3.5 text-[#16A34A]" />
                </div>
                <span>{b}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Button */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          onSelect(type);
          onContinue();
        }}
        className={`w-full py-3.5 px-6 rounded-xl font-bold text-sm transition-all duration-200 flex items-center justify-center gap-2 cursor-pointer ${
          selected
            ? 'bg-[#0F766E] text-white shadow-md hover:bg-[#065F46] hover:shadow-lg'
            : 'bg-[#FAFAF8] text-[#0F172A] border border-[#D6E8DE] hover:bg-[#ECFDF5] hover:border-[#0F766E]/40'
        }`}
      >
        <span>Continue as {isBrand ? 'Brand' : 'Recycler'}</span>
        <ArrowRight className="w-4 h-4" />
      </button>
    </motion.div>
  );
};
