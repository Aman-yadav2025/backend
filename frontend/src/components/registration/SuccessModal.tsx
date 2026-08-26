'use client';

import React from 'react';
import { motion } from 'motion/react';
import { useRouter } from 'next/navigation';
import {
  CheckCircle2,
  ShieldCheck,
  Download,
  LayoutDashboard,
  CreditCard,
} from 'lucide-react';
import { RegistrationData, PaymentResult } from '../../types/registration';
import { PrimaryButton } from './PrimaryButton';
import { SecondaryButton } from './SecondaryButton';

interface SuccessModalProps {
  data: RegistrationData;
  paymentResult: PaymentResult | null;
  onReset: () => void;
  onClose: () => void;
}

function formatPaise(paise: number): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(paise / 100);
}

export const SuccessModal: React.FC<SuccessModalProps> = ({
  data,
  paymentResult,
  onClose,
}) => {
  const router = useRouter();
  const displayOrderId = paymentResult?.razorpayOrderId ?? '—';
  const displayPaymentId = paymentResult?.razorpayPaymentId ?? '—';
  const displayAmount = paymentResult ? formatPaise(paymentResult.amountPaid) : '—';

  const dashboardPath = data.registrationType === 'recycler'
    ? '/recycler/dashboard'
    : '/brand/dashboard';

  const handleDownloadReceipt = () => {
    const lines = [
      '========================================================',
      'PUNARVRITT CIRCULAR ECONOMY MARKETPLACE',
      'PAYMENT & REGISTRATION RECEIPT',
      '========================================================',
      `Razorpay Order ID  : ${displayOrderId}`,
      `Razorpay Payment ID: ${displayPaymentId}`,
      `Amount Paid        : ${displayAmount}`,
      `Company Name       : ${data.companyInfo.companyName}`,
      `Registration Type  : ${data.registrationType.toUpperCase()}`,
      `Material Stream    : ${data.materialCategory.toUpperCase()}`,
      `Capacity Tier      : ${data.capacityTier.toUpperCase()}`,
      `Selected Plan      : ${data.subscriptionPlan.toUpperCase()} PLAN`,
      `GSTIN              : ${data.companyInfo.gstNumber}`,
      `PAN                : ${data.companyInfo.panNumber}`,
      `State              : ${data.companyInfo.state}`,
      `Status             : PAYMENT CAPTURED — PENDING CPCB VERIFICATION`,
      '========================================================',
    ];
    const blob = new Blob([lines.join('\n')], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${displayPaymentId}_Punarvritt_Receipt.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const goToDashboard = () => {
    onClose();
    router.push(dashboardPath);
  };

  return (
    <div className="fixed inset-0 z-[60] bg-slate-900/70 backdrop-blur-md flex items-center justify-center p-4 sm:p-6 overflow-y-auto">
      <motion.div
        initial={{ opacity: 0, scale: 0.9, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        className="bg-white rounded-3xl max-w-xl w-full p-6 sm:p-8 border border-[#D6E8DE] shadow-2xl relative text-center overflow-hidden"
      >
        {/* Background glow */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-64 h-32 bg-[#ECFDF5] rounded-full blur-2xl pointer-events-none" />

        {/* Icon */}
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ type: 'spring', stiffness: 260, damping: 20, delay: 0.1 }}
          className="w-20 h-20 rounded-3xl bg-[#0F766E] text-white flex items-center justify-center mx-auto mb-6 shadow-xl shadow-[#0F766E]/30 relative z-10"
        >
          <CheckCircle2 className="w-10 h-10" />
        </motion.div>

        <h2 className="text-2xl sm:text-3xl font-black text-[#0F172A] tracking-tight mb-2 relative z-10">
          Payment Successful!
        </h2>
        <p className="text-xs sm:text-sm text-slate-600 leading-relaxed max-w-md mx-auto mb-6 relative z-10">
          Your payment has been captured and your registration is now pending CPCB verification.
          You will receive a confirmation email shortly.
        </p>

        {/* Payment details card */}
        <div className="bg-[#FAFAF8] border border-[#D6E8DE] rounded-2xl p-4 mb-6 text-left relative z-10 space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-[#D6E8DE]">
            <div className="flex items-center gap-2 text-xs font-bold text-[#0F766E]">
              <CreditCard className="w-4 h-4" />
              <span>Payment Confirmation</span>
            </div>
            <span className="font-mono text-[10px] font-bold text-[#0F172A] bg-emerald-100 px-2 py-0.5 rounded truncate max-w-[160px]">
              {displayPaymentId}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <span className="text-slate-400 font-medium block">Company</span>
              <span className="font-bold text-[#0F172A] truncate block">
                {data.companyInfo.companyName}
              </span>
            </div>
            <div>
              <span className="text-slate-400 font-medium block">Amount Paid</span>
              <span className="font-bold text-[#16A34A] text-sm">{displayAmount}</span>
            </div>
            {paymentResult?.discountAmount && paymentResult.discountAmount > 0 ? (
              <>
                <div>
                  <span className="text-slate-400 font-medium block">Original Price</span>
                  <span className="font-bold text-slate-400 line-through text-sm">
                    {formatPaise(paymentResult.originalAmount)}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 font-medium block">Promo Saving</span>
                  <span className="font-bold text-[#16A34A]">
                    − {formatPaise(paymentResult.discountAmount)}
                    {paymentResult.promoCode && (
                      <span className="ml-1 font-mono text-[10px] bg-[#ECFDF5] text-[#0F766E] px-1.5 py-0.5 rounded">
                        {paymentResult.promoCode}
                      </span>
                    )}
                  </span>
                </div>
              </>
            ) : null}
            <div>
              <span className="text-slate-400 font-medium block">Account Type</span>
              <span className="font-bold text-[#0F766E] capitalize">
                {data.registrationType} · {data.materialCategory}
              </span>
            </div>
            <div>
              <span className="text-slate-400 font-medium block">Plan</span>
              <span className="font-bold text-[#0F172A] capitalize">
                {data.subscriptionPlan} · {data.capacityTier.toUpperCase()}
              </span>
            </div>
            <div className="col-span-2">
              <span className="text-slate-400 font-medium block">Order ID</span>
              <span className="font-mono font-bold text-[10px] text-slate-600 break-all">
                {displayOrderId}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2 pt-2 border-t border-[#D6E8DE]">
            <ShieldCheck className="w-4 h-4 text-[#0F766E]" />
            <span className="text-xs font-bold text-[#0F766E]">
              Registration Submitted — Pending CPCB Verification
            </span>
          </div>
        </div>

        {/* Actions */}
        <div className="space-y-3 relative z-10">
          <PrimaryButton
            onClick={goToDashboard}
            fullWidth
            size="lg"
            icon={<LayoutDashboard className="w-5 h-5" />}
          >
            Go to My Dashboard
          </PrimaryButton>

          <SecondaryButton
            onClick={handleDownloadReceipt}
            fullWidth
            size="md"
            icon={<Download className="w-4 h-4" />}
          >
            Download Payment Receipt
          </SecondaryButton>
        </div>
      </motion.div>
    </div>
  );
};
