'use client';

import React, { useState, forwardRef } from 'react';
import { Eye, EyeOff, Lock } from 'lucide-react';
import { Input, InputProps } from '../ui/Input';

export interface PasswordInputProps extends Omit<InputProps, 'type'> {
  showStrengthMeter?: boolean;
}

export const PasswordInput = forwardRef<HTMLInputElement, PasswordInputProps>(({
  showStrengthMeter = false,
  value,
  onChange,
  ...props
}, ref) => {
  const [showPassword, setShowPassword] = useState(false);

  const togglePasswordVisibility = () => {
    setShowPassword((prev) => !prev);
  };

  // Basic strength check calculation
  const getStrength = (val: string) => {
    if (!val) return 0;
    let score = 0;
    if (val.length >= 8) score += 1;
    if (/[A-Z]/.test(val)) score += 1;
    if (/[0-9]/.test(val)) score += 1;
    if (/[^A-Za-z0-9]/.test(val)) score += 1;
    return score;
  };

  const strValue = typeof value === 'string' ? value : '';
  const strengthScore = getStrength(strValue);

  const getStrengthLabel = () => {
    if (strengthScore === 0) return { label: 'Weak', color: 'bg-red-500' };
    if (strengthScore === 1) return { label: 'Weak', color: 'bg-red-500' };
    if (strengthScore === 2) return { label: 'Fair', color: 'bg-amber-500' };
    if (strengthScore === 3) return { label: 'Good', color: 'bg-blue-500' };
    return { label: 'Strong', color: 'bg-emerald-600' };
  };

  const strengthInfo = getStrengthLabel();

  return (
    <div className="space-y-1.5">
      <Input
        ref={ref}
        type={showPassword ? 'text' : 'password'}
        leftIcon={<Lock className="w-4 h-4" />}
        rightIcon={
          <button
            type="button"
            onClick={togglePasswordVisibility}
            className="p-1 text-slate-400 hover:text-slate-600 focus:outline-none cursor-pointer"
            tabIndex={-1}
            aria-label={showPassword ? 'Hide password' : 'Show password'}
          >
            {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        }
        value={value}
        onChange={onChange}
        {...props}
      />

      {showStrengthMeter && strValue.length > 0 && (
        <div className="pt-1">
          <div className="flex items-center justify-between text-[11px] text-slate-500 mb-1">
            <span>Password strength:</span>
            <span className="font-semibold text-slate-700">{strengthInfo.label}</span>
          </div>
          <div className="flex gap-1 h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
            {[1, 2, 3, 4].map((step) => (
              <div
                key={step}
                className={`h-full flex-1 transition-all duration-300 ${
                  step <= strengthScore ? strengthInfo.color : 'bg-slate-200'
                }`}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
});

PasswordInput.displayName = 'PasswordInput';
