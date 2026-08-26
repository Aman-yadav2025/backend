'use client';

import React from 'react';
import { motion } from 'motion/react';
import { Sparkles, CheckCircle, ShieldCheck } from 'lucide-react';

interface AnimatedBadgeProps {
  children: React.ReactNode;
  variant?: 'popular' | 'success' | 'verified' | 'tier';
  className?: string;
}

export const AnimatedBadge: React.FC<AnimatedBadgeProps> = ({
  children,
  variant = 'popular',
  className = '',
}) => {
  const styles = {
    popular: 'bg-gradient-to-r from-[#0F766E] to-[#065F46] text-white shadow-sm shadow-[#0F766E]/30',
    success: 'bg-[#ECFDF5] text-[#16A34A] border border-[#16A34A]/30',
    verified: 'bg-[#ECFDF5] text-[#0F766E] border border-[#D6E8DE]',
    tier: 'bg-emerald-100 text-[#065F46] font-bold border border-emerald-300',
  };

  const icons = {
    popular: <Sparkles className="w-3 h-3 text-amber-300 animate-pulse" />,
    success: <CheckCircle className="w-3.5 h-3.5 text-[#16A34A]" />,
    verified: <ShieldCheck className="w-3.5 h-3.5 text-[#0F766E]" />,
    tier: <span className="w-1.5 h-1.5 rounded-full bg-[#065F46] animate-ping" />,
  };

  return (
    <motion.span
      initial={{ scale: 0.9, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold tracking-wide uppercase ${styles[variant]} ${className}`}
    >
      {icons[variant]}
      <span>{children}</span>
    </motion.span>
  );
};
