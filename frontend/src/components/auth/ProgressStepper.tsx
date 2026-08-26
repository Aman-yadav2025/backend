'use client';

import React from 'react';
import { Check } from 'lucide-react';

interface Step {
  id: number;
  name: string;
  description?: string;
}

interface ProgressStepperProps {
  steps: Step[];
  currentStep: number;
}

export const ProgressStepper: React.FC<ProgressStepperProps> = ({ steps, currentStep }) => {
  return (
    <div className="w-full mb-8 sm:mb-10">
      <div className="flex items-center justify-between relative max-w-2xl mx-auto">
        {/* Background Connecting Line */}
        <div className="absolute top-4 left-6 right-6 h-0.5 bg-slate-200 -z-0" />
        
        {/* Active Progress Line */}
        <div 
          className="absolute top-4 left-6 h-0.5 bg-emerald-600 transition-all duration-300 ease-out -z-0"
          style={{
            width: `${((Math.min(currentStep, steps.length) - 1) / (steps.length - 1)) * 100}%`
          }}
        />

        {steps.map((step) => {
          const isCompleted = step.id < currentStep;
          const isCurrent = step.id === currentStep;

          return (
            <div key={step.id} className="flex flex-col items-center relative z-10">
              <div
                className={`
                  w-8 h-8 sm:w-9 sm:h-9 rounded-full flex items-center justify-center font-bold text-xs sm:text-sm
                  transition-all duration-200 border-2
                  ${
                    isCompleted
                      ? 'bg-emerald-600 border-emerald-600 text-white shadow-sm'
                      : isCurrent
                      ? 'bg-white border-emerald-600 text-emerald-700 shadow-md ring-4 ring-emerald-100'
                      : 'bg-white border-slate-300 text-slate-400'
                  }
                `}
              >
                {isCompleted ? <Check className="w-4 h-4 stroke-[3]" /> : step.id}
              </div>
              <div className="mt-2 text-center">
                <span
                  className={`block text-xs font-semibold tracking-tight ${
                    isCurrent
                      ? 'text-emerald-700 font-bold'
                      : isCompleted
                      ? 'text-slate-800'
                      : 'text-slate-400'
                  }`}
                >
                  {step.name}
                </span>
                {step.description && (
                  <span className="hidden sm:block text-[10px] text-slate-400 font-normal mt-0.5">
                    {step.description}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
