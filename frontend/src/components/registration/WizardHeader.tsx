'use client';

import React from 'react';
import { Recycle, BookmarkCheck, X, Check } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';

interface WizardHeaderProps {
  currentStep: number;
  totalSteps: number;
  stepTitle: string;
  onSaveProgress: () => void;
  onClose: () => void;
  saveToast: boolean;
}

export const WizardHeader: React.FC<WizardHeaderProps> = ({
  currentStep,
  totalSteps,
  stepTitle,
  onSaveProgress,
  onClose,
  saveToast,
}) => {
  return (
    <div className="relative z-20 border-b border-[#D6E8DE] bg-white px-4 sm:px-8 py-4 flex flex-col sm:flex-row items-center justify-between gap-4 shadow-xs">
      {/* Brand & Title */}
      <div className="flex items-center gap-3 w-full sm:w-auto justify-between sm:justify-start">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-[#0F766E] flex items-center justify-center text-white shadow-sm shadow-[#0F766E]/30">
            <Recycle className="w-5 h-5 animate-spin-slow" />
          </div>
          <div>
            <span className="font-black text-lg text-[#0F172A] tracking-tight block">
              Punarvritt
            </span>
            <span className="text-[10px] font-bold tracking-widest uppercase text-[#0F766E] block -mt-1">
              Registration Wizard
            </span>
          </div>
        </div>

        <div className="hidden sm:block h-6 w-px bg-[#D6E8DE] mx-1" />

        <div className="text-right sm:text-left">
          <span className="text-xs font-semibold text-slate-500 block">
            Step {currentStep} of {totalSteps}
          </span>
          <span className="text-sm font-bold text-[#0F172A] block truncate max-w-[200px] sm:max-w-xs">
            {stepTitle}
          </span>
        </div>

        {/* Mobile Close Button */}
        <button
          onClick={onClose}
          className="sm:hidden p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
          aria-label="Close registration wizard"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3 w-full sm:w-auto justify-end">
        {/* Save Progress Button */}
        <div className="relative">
          <button
            onClick={onSaveProgress}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold text-[#0F766E] bg-[#ECFDF5] border border-[#D6E8DE] hover:bg-emerald-100/80 transition-all cursor-pointer"
          >
            <BookmarkCheck className="w-4 h-4 text-[#0F766E]" />
            <span>Save Progress</span>
          </button>

          <AnimatePresence>
            {saveToast && (
              <motion.div
                initial={{ opacity: 0, y: 10, scale: 0.9 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -10, scale: 0.9 }}
                className="absolute right-0 top-10 z-30 bg-[#065F46] text-white text-xs px-3 py-1.5 rounded-lg shadow-lg flex items-center gap-1.5 whitespace-nowrap"
              >
                <Check className="w-3.5 h-3.5 text-emerald-300" />
                <span>Draft saved locally!</span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Desktop Close Button */}
        <button
          onClick={onClose}
          className="hidden sm:flex items-center gap-1 px-3 py-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
          aria-label="Close modal"
        >
          <X className="w-4 h-4" />
          <span>Exit</span>
        </button>
      </div>
    </div>
  );
};
