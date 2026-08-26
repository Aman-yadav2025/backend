'use client';

import React, { forwardRef } from 'react';
import { Check } from 'lucide-react';

export interface CheckboxProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: React.ReactNode;
  error?: string;
}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(({
  label,
  error,
  className = '',
  id,
  checked,
  onChange,
  ...props
}, ref) => {
  const checkboxId = id || `checkbox-${Math.random().toString(36).substring(2, 9)}`;

  return (
    <div className="flex flex-col space-y-1">
      <label htmlFor={checkboxId} className="inline-flex items-start gap-3 cursor-pointer group select-none">
        <div className="relative flex items-center shrink-0 mt-0.5">
          <input
            ref={ref}
            id={checkboxId}
            type="checkbox"
            checked={checked}
            onChange={onChange}
            className="sr-only peer"
            {...props}
          />
          <div className={`
            w-5 h-5 rounded-md border text-white flex items-center justify-center transition-all duration-200
            peer-focus:ring-2 peer-focus:ring-emerald-500/20
            ${
              checked
                ? 'bg-emerald-600 border-emerald-600'
                : 'border-slate-300 bg-white group-hover:border-slate-400'
            }
            ${error ? 'border-red-500' : ''}
          `}>
            {checked && <Check className="w-3.5 h-3.5 stroke-[3]" />}
          </div>
        </div>
        {label && (
          <span className="text-xs sm:text-sm text-slate-600 font-medium leading-snug">
            {label}
          </span>
        )}
      </label>
      {error && (
        <p className="text-xs font-medium text-red-600 flex items-center gap-1 pl-8">
          <span>•</span> {error}
        </p>
      )}
    </div>
  );
});

Checkbox.displayName = 'Checkbox';
