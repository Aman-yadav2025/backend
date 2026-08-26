'use client';

import React from 'react';
import { motion } from 'motion/react';
import { Check, User, Recycle, Building2, FileText, Scale, CreditCard, ClipboardCheck } from 'lucide-react';

interface StepperProps {
  currentStep: number;
  totalSteps: number;
  onStepClick: (step: number) => void;
}

const STEP_ITEMS = [
  { step: 1, label: 'Type', title: 'Choose Type & Role', icon: User },
  { step: 2, label: 'Company', title: 'Company Details', icon: Building2 },
  { step: 3, label: 'Documents', title: 'Upload Documents', icon: FileText },
  { step: 4, label: 'Material', title: 'Select Material', icon: Recycle },
  { step: 5, label: 'Capacity', title: 'Annual Capacity', icon: Scale },
  { step: 6, label: 'Plan', title: 'Subscription Plan', icon: CreditCard },
  { step: 7, label: 'Summary', title: 'Review & Submit', icon: ClipboardCheck },
];

export const Stepper: React.FC<StepperProps> = ({ currentStep, totalSteps, onStepClick }) => {
  const progressPercent = Math.round(((currentStep - 1) / (STEP_ITEMS.length - 1)) * 100);

  return (
    <div className="bg-[#FAFAF8] border-b border-[#D6E8DE] px-4 sm:px-8 py-3 sm:py-4">
      <div className="max-w-5xl mx-auto">
        {/* Progress Bar background track */}
        <div className="relative mb-3 sm:mb-4">
          <div className="h-1.5 w-full bg-[#D6E8DE]/60 rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-gradient-to-r from-[#0F766E] to-[#16A34A]"
              initial={{ width: 0 }}
              animate={{ width: `${progressPercent}%` }}
              transition={{ duration: 0.3, ease: 'easeInOut' }}
            />
          </div>
        </div>

        {/* Stepper Nodes */}
        <div className="flex items-center justify-between relative">
          {STEP_ITEMS.map((item) => {
            const isCompleted = item.step < currentStep;
            const isCurrent = item.step === currentStep;
            const Icon = item.icon;

            return (
              <button
                key={item.step}
                onClick={() => isCompleted && onStepClick(item.step)}
                disabled={!isCompleted && !isCurrent}
                className={`flex flex-col items-center group focus:outline-none ${
                  isCompleted ? 'cursor-pointer' : isCurrent ? 'cursor-default' : 'cursor-not-allowed opacity-60'
                }`}
              >
                {/* Number Circle */}
                <motion.div
                  whileHover={isCompleted ? { scale: 1.1 } : {}}
                  className={`w-8 h-8 sm:w-10 sm:h-10 rounded-full flex items-center justify-center font-bold text-xs sm:text-sm transition-all duration-200 border-2 ${
                    isCompleted
                      ? 'bg-[#0F766E] border-[#0F766E] text-white shadow-xs'
                      : isCurrent
                      ? 'bg-white border-[#0F766E] text-[#0F766E] shadow-md shadow-[#0F766E]/20 ring-4 ring-[#ECFDF5]'
                      : 'bg-white border-slate-300 text-slate-400'
                  }`}
                >
                  {isCompleted ? (
                    <Check className="w-4 h-4 sm:w-5 sm:h-5 text-white" />
                  ) : (
                    <Icon className="w-4 h-4 sm:w-5 sm:h-5" />
                  )}
                </motion.div>

                {/* Step Name (Desktop) */}
                <span
                  className={`mt-1.5 text-[11px] font-semibold hidden md:block transition-colors ${
                    isCurrent
                      ? 'text-[#0F766E] font-bold'
                      : isCompleted
                      ? 'text-[#0F172A]'
                      : 'text-slate-400'
                  }`}
                >
                  {item.label}
                </span>
              </button>
            );
          })}
        </div>

        {/* Mobile active step label */}
        <div className="mt-2 text-center md:hidden">
          <span className="text-xs font-bold text-[#0F766E]">
            Step {currentStep} of {totalSteps}: {STEP_ITEMS[currentStep - 1]?.title}
          </span>
        </div>
      </div>
    </div>
  );
};
