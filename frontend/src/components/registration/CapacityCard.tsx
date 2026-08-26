import React from 'react';
import { motion } from 'motion/react';
import { Scale, CheckCircle2, Factory, ShieldCheck, Zap, Layers, Recycle, Anvil } from 'lucide-react';
import { CapacityTier, RegistrationType, MaterialCategory } from '../../types/registration';
import { getCapacityTiers } from '../../data/pricing';

interface CapacityCardProps {
  registrationType?: RegistrationType;
  materialCategory?: MaterialCategory;
  selectedTier?: CapacityTier;
  onSelect?: (tier: CapacityTier) => void;
  plasticTier?: CapacityTier;
  metalTier?: CapacityTier;
  onSelectPlasticTier?: (tier: CapacityTier) => void;
  onSelectMetalTier?: (tier: CapacityTier) => void;
}

export const CapacityCard: React.FC<CapacityCardProps> = ({
  registrationType,
  materialCategory,
  selectedTier = 'tier2',
  onSelect,
  plasticTier = 'tier2',
  metalTier = 'tier2',
  onSelectPlasticTier,
  onSelectMetalTier,
}) => {
  const isDualMaterial = materialCategory === 'plastic_and_metal';
  const tiers = getCapacityTiers(registrationType);

  const getTierIcon = (id: CapacityTier) => {
    switch (id) {
      case 'tier1':
        return <Scale className="w-5 h-5" />;
      case 'tier2':
        return <Layers className="w-5 h-5" />;
      case 'tier3':
        return <Factory className="w-5 h-5" />;
      case 'tier4':
        return <Zap className="w-5 h-5" />;
    }
  };

  if (isDualMaterial) {
    return (
      <div className="space-y-8">
        {/* Plastic Capacity Section */}
        <div className="bg-emerald-50/40 p-5 sm:p-6 rounded-2xl border border-emerald-200/70">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-[#0F766E] text-white flex items-center justify-center shadow-xs">
              <Recycle className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-[#0F172A]">Plastic Capacity Tier</h3>
              <p className="text-xs text-slate-500">Select annual plastic waste processing/purchasing volume</p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {tiers.map((tier) => {
              const isSelected = plasticTier === tier.id;
              return (
                <div
                  key={`plastic-${tier.id}`}
                  onClick={() => onSelectPlasticTier && onSelectPlasticTier(tier.id)}
                  className={`p-4 rounded-xl border-2 transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-white border-[#0F766E] shadow-md ring-2 ring-[#0F766E]/20'
                      : 'bg-white/70 border-slate-200 hover:border-slate-300'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-black uppercase text-[#0F766E]">{tier.title}</span>
                    {isSelected && <CheckCircle2 className="w-4 h-4 text-[#0F766E]" />}
                  </div>
                  <div className="text-sm font-black text-slate-900">{tier.range}</div>
                  <div className="text-[11px] text-slate-500 mt-1 line-clamp-2">{tier.description}</div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Metal Capacity Section */}
        <div className="bg-slate-100/60 p-5 sm:p-6 rounded-2xl border border-slate-200">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-slate-800 text-white flex items-center justify-center shadow-xs">
              <Anvil className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-[#0F172A]">Metal Capacity Tier</h3>
              <p className="text-xs text-slate-500">Select annual metallic packaging processing/purchasing volume</p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {tiers.map((tier) => {
              const isSelected = metalTier === tier.id;
              return (
                <div
                  key={`metal-${tier.id}`}
                  onClick={() => onSelectMetalTier && onSelectMetalTier(tier.id)}
                  className={`p-4 rounded-xl border-2 transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-white border-slate-800 shadow-md ring-2 ring-slate-800/20'
                      : 'bg-white/70 border-slate-200 hover:border-slate-300'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-black uppercase text-slate-800">{tier.title}</span>
                    {isSelected && <CheckCircle2 className="w-4 h-4 text-slate-800" />}
                  </div>
                  <div className="text-sm font-black text-slate-900">{tier.range}</div>
                  <div className="text-[11px] text-slate-500 mt-1 line-clamp-2">{tier.description}</div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Selected Summary Callout */}
        <div className="bg-[#0F766E] text-white rounded-2xl p-5 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <ShieldCheck className="w-6 h-6 text-emerald-300 shrink-0" />
            <div>
              <span className="text-xs font-bold text-emerald-200 block">Dual Material Selection Active</span>
              <p className="text-xs text-white/90">
                Plastic: <span className="font-bold text-emerald-300">{tiers.find((t) => t.id === plasticTier)?.range}</span> | Metal: <span className="font-bold text-emerald-300">{tiers.find((t) => t.id === metalTier)?.range}</span>
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const selectedDetail = tiers.find((t) => t.id === selectedTier) || tiers[1];

  return (
    <div>
      {/* 4 Tier Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5 mb-8">
        {tiers.map((tier) => {
          const isSelected = selectedTier === tier.id;

          return (
            <motion.div
              key={tier.id}
              whileHover={{ y: -3 }}
              whileTap={{ scale: 0.98 }}
              animate={{
                scale: isSelected ? 1.02 : 1,
                borderColor: isSelected ? '#0F766E' : '#D6E8DE',
              }}
              onClick={() => onSelect && onSelect(tier.id)}
              className={`relative p-5 rounded-2xl border-2 transition-all duration-300 cursor-pointer flex flex-col justify-between ${
                isSelected
                  ? 'bg-[#ECFDF5]/70 border-[#0F766E] shadow-lg shadow-[#0F766E]/15 ring-2 ring-[#0F766E]/20'
                  : 'bg-white border-[#D6E8DE] shadow-xs hover:border-[#0F766E]/50 hover:shadow-md'
              }`}
            >
              <div className="flex items-center justify-between mb-4">
                <div
                  className={`w-10 h-10 rounded-xl flex items-center justify-center transition-colors ${
                    isSelected
                      ? 'bg-[#0F766E] text-white shadow-md shadow-[#0F766E]/30'
                      : 'bg-slate-100 text-slate-600'
                  }`}
                >
                  {getTierIcon(tier.id)}
                </div>

                {isSelected ? (
                  <div className="w-5 h-5 rounded-full bg-[#0F766E] text-white flex items-center justify-center shadow-xs">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                  </div>
                ) : (
                  <div className="w-5 h-5 rounded-full border-2 border-slate-300" />
                )}
              </div>

              <div>
                <span className="text-[10px] font-extrabold uppercase tracking-widest text-[#0F766E] block mb-1">
                  {tier.title}
                </span>
                <h4 className="text-lg font-black text-[#0F172A] tracking-tight mb-2">
                  {tier.range}
                </h4>
                <p className="text-xs text-slate-600 leading-relaxed mb-4">
                  {tier.description}
                </p>
              </div>

              <div className="pt-3 border-t border-[#D6E8DE]/80">
                <span
                  className={`text-[10px] font-bold px-2.5 py-1 rounded-md block truncate text-center ${
                    isSelected
                      ? 'bg-[#0F766E] text-white'
                      : 'bg-slate-100 text-slate-500'
                  }`}
                >
                  {tier.recommendedFor}
                </span>
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* Selected Tier Callout Box */}
      <motion.div
        key={selectedDetail.id}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-gradient-to-r from-[#0F766E] to-[#065F46] text-white rounded-2xl p-6 sm:p-7 shadow-xl shadow-[#0F766E]/20 relative overflow-hidden flex flex-col sm:flex-row items-center justify-between gap-4"
      >
        <div className="relative z-10 flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-white/20 backdrop-blur-md flex items-center justify-center text-white shrink-0">
            <ShieldCheck className="w-7 h-7 text-emerald-300" />
          </div>
          <div>
            <span className="text-xs font-bold uppercase tracking-widest text-emerald-200 block">
              Selected Processing Capacity Tier
            </span>
            <h3 className="text-xl sm:text-2xl font-black tracking-tight mt-0.5">
              You are in <span className="text-emerald-300">{selectedDetail.title}</span> ({selectedDetail.range})
            </h3>
            <p className="text-xs text-emerald-100/90 mt-1">
              Your subscription plan pricing in the next step will automatically adjust to this capacity band.
            </p>
          </div>
        </div>

        <div className="relative z-10 shrink-0 bg-white/10 backdrop-blur-md px-4 py-2 rounded-xl border border-white/20 text-center">
          <span className="text-[10px] uppercase font-bold text-emerald-200 block">
            Annual Tonnage Range
          </span>
          <span className="text-lg font-black text-white">{selectedDetail.range}</span>
        </div>
      </motion.div>
    </div>
  );
};
