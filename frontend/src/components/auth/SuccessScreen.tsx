'use client';

import React from 'react';
import { CheckCircle2, ArrowRight, Home, ShieldCheck } from 'lucide-react';
import { Button } from '../ui/Button';
import { useRouter } from 'next/navigation';

interface SuccessScreenProps {
  userType: 'brand' | 'recycler';
  companyName?: string;
}

export const SuccessScreen: React.FC<SuccessScreenProps> = ({
  userType,
  companyName = 'your company',
}) => {
  const router = useRouter();

  const dashboardPath = userType === 'brand' ? '/brand/dashboard' : '/recycler/dashboard';

  return (
    <div className="bg-white rounded-2xl border border-slate-200/80 p-8 sm:p-12 shadow-sm max-w-2xl mx-auto text-center animate-in fade-in zoom-in duration-300">
      <div className="w-20 h-20 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto mb-6 shadow-sm ring-8 ring-emerald-50">
        <CheckCircle2 className="w-12 h-12 stroke-[2]" />
      </div>

      <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold mb-3">
        <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
        <span>Punarvritt Certified Account</span>
      </div>

      <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
        Registration Successful
      </h2>

      <p className="mt-3 text-slate-600 text-sm sm:text-base max-w-md mx-auto leading-relaxed">
        Your {userType} account for <strong className="text-slate-900 font-semibold">{companyName}</strong> has been created successfully. Welcome to the Punarvritt EPR circular economy network!
      </p>

      <div className="mt-8 pt-6 border-t border-slate-100 flex flex-col sm:flex-row items-center justify-center gap-3">
        <Button
          variant="primary"
          size="lg"
          fullWidth
          icon={<ArrowRight className="w-4 h-4" />}
          iconPosition="right"
          onClick={() => router.push(dashboardPath)}
        >
          Go to Dashboard
        </Button>

        <Button
          variant="outline"
          size="lg"
          fullWidth
          icon={<Home className="w-4 h-4" />}
          iconPosition="left"
          onClick={() => router.push('/')}
        >
          Back to Home
        </Button>
      </div>
    </div>
  );
};
