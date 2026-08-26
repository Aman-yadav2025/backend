'use client';

import React from 'react';
import { RegistrationData, SubscriptionPlanId } from '../../types/registration';
import { CAPACITY_TIERS, PRICING_MATRIX, PLAN_DETAILS, PRICE_AMOUNTS } from '../../data/pricing';
import {
  Building2,
  Package,
  FileCheck2,
  CreditCard,
  CheckCircle2,
  Edit3,
  ArrowRight,
} from 'lucide-react';
import { PromoCodeInput } from './PromoCodeInput';

interface SummaryCardProps {
  data: RegistrationData;
  onGoToStep: (step: number) => void;
  // promo props passed down from wizard
  appliedPromoCode: string | null;
  promoDiscountAmount: number;
  promoFinalAmount: number;
  promoOriginalAmount: number;
  onApplyPromo: (code: string, discountAmount: number, finalAmount: number, originalAmount: number) => void;
  onRemovePromo: () => void;
}

function formatPaise(paise: number): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(paise / 100);
}

const DOC_LABELS: Record<string, string> = {
  gst: 'GST Certificate',
  pan: 'PAN Card',
  factory_license: 'Factory License',
  pollution_cert: 'Pollution Certificate',
  coi_cert: 'Certificate of Incorporation',
  cancelled_cheque: 'Cancelled Cheque',
  auth_letter: 'Authorized Signatory Letter',
  recycler_cert: 'Recycler Authorized Certification',
  epr_cert: 'EPR Certificate',
};

export const SummaryCard: React.FC<SummaryCardProps> = ({
  data,
  onGoToStep,
  appliedPromoCode,
  promoDiscountAmount,
  promoFinalAmount,
  promoOriginalAmount,
  onApplyPromo,
  onRemovePromo,
}) => {
  const isBrand = data.registrationType === 'brand';
  const tierInfo = CAPACITY_TIERS.find((t) => t.id === data.capacityTier) || CAPACITY_TIERS[1];
  const planInfo = PLAN_DETAILS.find((p) => p.id === data.subscriptionPlan) || PLAN_DETAILS[1];
  const priceInfo = PRICING_MATRIX[data.capacityTier]?.[data.subscriptionPlan as SubscriptionPlanId];
  const baseAmountPaise = PRICE_AMOUNTS[data.capacityTier]?.[data.subscriptionPlan] ?? 0;
  const isCustomPlan = baseAmountPaise === 0;

  const displayOriginal = appliedPromoCode ? promoOriginalAmount : baseAmountPaise;
  const displayFinal = appliedPromoCode ? promoFinalAmount : baseAmountPaise;
  const displayDiscount = appliedPromoCode ? promoDiscountAmount : 0;

  const docKeys = isBrand
    ? ['gst', 'pan', 'factory_license', 'coi_cert', 'epr_cert', 'cancelled_cheque']
    : ['gst', 'pan', 'factory_license', 'pollution_cert', 'coi_cert', 'auth_letter', 'cancelled_cheque', 'recycler_cert', 'epr_cert'];

  return (
    <div className="space-y-6">
      {/* All-steps banner */}
      <div className="bg-[#ECFDF5] border border-[#D6E8DE] rounded-2xl p-4 sm:p-5 flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-[#0F766E] text-white flex items-center justify-center shrink-0">
          <CheckCircle2 className="w-6 h-6" />
        </div>
        <div>
          <h4 className="text-sm font-bold text-[#0F172A]">All Steps Validated</h4>
          <p className="text-xs text-slate-600">
            Review your registration summary below before submitting to the Punarvritt registry.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Registration Profile */}
        <div className="bg-white rounded-2xl border border-[#D6E8DE] p-6 shadow-xs relative">
          <button onClick={() => onGoToStep(1)} className="absolute top-5 right-5 p-1.5 text-slate-400 hover:text-[#0F766E] rounded-lg hover:bg-[#ECFDF5] transition-colors cursor-pointer" title="Edit">
            <Edit3 className="w-4 h-4" />
          </button>
          <div className="flex items-center gap-2.5 mb-4 text-[#0F766E] font-bold text-xs uppercase tracking-wider">
            <Package className="w-4 h-4" />
            <span>Registration Profile</span>
          </div>
          <div className="space-y-4">
            <div>
              <span className="text-xs text-slate-400 block font-medium">Account Type</span>
              <span className="text-base font-extrabold text-[#0F172A]">
                {isBrand
                  ? data.brandSubRole === 'brand_employee'
                    ? 'Brand Owner / PIBO (Brand Employee)'
                    : 'Brand Owner / PIBO (Brand Admin)'
                  : 'Plastic Recycler / Aggregator'}
              </span>
            </div>
            <div>
              <span className="text-xs text-slate-400 block font-medium">Primary Material Stream</span>
              <span className="text-base font-extrabold text-[#0F172A]">
                {data.materialCategory === 'plastic_and_metal'
                  ? 'Plastic & Metal Circularity'
                  : data.materialCategory === 'metal'
                  ? 'Metal Circularity'
                  : 'Plastic Circularity'}
              </span>
            </div>
          </div>
        </div>

        {/* Capacity & Subscription + Promo + Price Summary */}
        <div className="bg-white rounded-2xl border border-[#D6E8DE] p-6 shadow-xs relative">
          <button onClick={() => onGoToStep(4)} className="absolute top-5 right-5 p-1.5 text-slate-400 hover:text-[#0F766E] rounded-lg hover:bg-[#ECFDF5] transition-colors cursor-pointer" title="Edit">
            <Edit3 className="w-4 h-4" />
          </button>
          <div className="flex items-center gap-2.5 mb-4 text-[#0F766E] font-bold text-xs uppercase tracking-wider">
            <CreditCard className="w-4 h-4" />
            <span>Capacity & Subscription</span>
          </div>

          <div className="space-y-3 mb-5">
            <div>
              <span className="text-xs text-slate-400 block font-medium">Annual Tonnage Tier</span>
              {data.materialCategory === 'plastic_and_metal' ? (
                <div className="text-sm font-extrabold text-[#0F172A] space-y-0.5">
                  <div>Plastic: <span className="text-[#0F766E]">{CAPACITY_TIERS.find((t) => t.id === (data.plasticCapacityTier || 'tier2'))?.range}</span></div>
                  <div>Metal: <span className="text-[#0F766E]">{CAPACITY_TIERS.find((t) => t.id === (data.metalCapacityTier || 'tier2'))?.range}</span></div>
                </div>
              ) : (
                <span className="text-base font-extrabold text-[#0F172A]">
                  {tierInfo.title} ({tierInfo.range})
                </span>
              )}
            </div>
            <div>
              <span className="text-xs text-slate-400 block font-medium">Selected Plan</span>
              <div className="flex items-baseline gap-2">
                <span className="text-base font-extrabold text-[#0F766E]">{planInfo.name} Plan</span>
                <span className="text-xs font-bold text-slate-500">• {priceInfo?.period}</span>
              </div>
            </div>
          </div>

          {/* Promo code input (hidden for custom-quoted plans) */}
          {!isCustomPlan && (
            <div className="mb-4">
              <PromoCodeInput
                capacityTier={data.capacityTier}
                subscriptionPlan={data.subscriptionPlan}
                registrationType={data.registrationType as 'brand' | 'recycler'}
                appliedCode={appliedPromoCode}
                discountAmount={promoDiscountAmount}
                onApply={onApplyPromo}
                onRemove={onRemovePromo}
              />
            </div>
          )}

          {/* Price breakdown */}
          {!isCustomPlan ? (
            <div className="rounded-xl border border-[#D6E8DE] bg-[#FAFAF8] p-4 space-y-2 text-xs">
              <div className="flex justify-between text-slate-500">
                <span>Plan price</span>
                <span className={appliedPromoCode ? 'line-through text-slate-400' : 'font-bold text-[#0F172A]'}>
                  {formatPaise(displayOriginal)}
                </span>
              </div>
              {appliedPromoCode && (
                <div className="flex justify-between text-[#16A34A] font-bold">
                  <span className="flex items-center gap-1">
                    Promo discount
                    <span className="font-mono text-[10px] bg-[#ECFDF5] px-1.5 py-0.5 rounded text-[#0F766E]">
                      {appliedPromoCode}
                    </span>
                  </span>
                  <span>− {formatPaise(displayDiscount)}</span>
                </div>
              )}
              <div className="flex justify-between pt-2 border-t border-[#D6E8DE] font-bold text-[#0F172A]">
                <span>Total due</span>
                <span className="text-base font-black text-[#0F766E]">{formatPaise(displayFinal)}</span>
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 font-semibold flex items-center gap-2">
              <ArrowRight className="w-3.5 h-3.5 shrink-0" />
              Custom pricing — our team will reach out to finalise your quote.
            </div>
          )}
        </div>

        {/* Company Info */}
        <div className="bg-white rounded-2xl border border-[#D6E8DE] p-6 shadow-xs md:col-span-2 relative">
          <button onClick={() => onGoToStep(2)} className="absolute top-5 right-5 p-1.5 text-slate-400 hover:text-[#0F766E] rounded-lg hover:bg-[#ECFDF5] transition-colors cursor-pointer" title="Edit">
            <Edit3 className="w-4 h-4" />
          </button>
          <div className="flex items-center gap-2.5 mb-4 text-[#0F766E] font-bold text-xs uppercase tracking-wider">
            <Building2 className="w-4 h-4" />
            <span>Company Information</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 text-xs">
            <div>
              <span className="text-slate-400 font-medium block">Company Name</span>
              <span className="font-bold text-[#0F172A] text-sm">{data.companyInfo.companyName || 'N/A'}</span>
            </div>
            <div>
              <span className="text-slate-400 font-medium block">Official Email</span>
              <span className="font-bold text-[#0F172A]">{data.companyInfo.companyEmail || 'N/A'}</span>
            </div>
            <div>
              <span className="text-slate-400 font-medium block">Mobile Number</span>
              <span className="font-bold text-[#0F172A]">{data.companyInfo.mobileNumber || 'N/A'}</span>
            </div>
            <div>
              <span className="text-slate-400 font-medium block">GSTIN</span>
              <span className="font-bold text-[#0F172A] tracking-wider uppercase">{data.companyInfo.gstNumber || 'N/A'}</span>
            </div>
            <div>
              <span className="text-slate-400 font-medium block">PAN Number</span>
              <span className="font-bold text-[#0F172A] tracking-wider uppercase">{data.companyInfo.panNumber || 'N/A'}</span>
            </div>
            <div>
              <span className="text-slate-400 font-medium block">Contact Person</span>
              <span className="font-bold text-[#0F172A]">
                {data.companyInfo.contactPerson} ({data.companyInfo.designation})
              </span>
            </div>
            <div className="sm:col-span-2 md:col-span-3">
              <span className="text-slate-400 font-medium block">Facility Address</span>
              <span className="font-bold text-[#0F172A]">
                {data.companyInfo.factoryAddress}, {data.companyInfo.city}, {data.companyInfo.state} — {data.companyInfo.pincode}
              </span>
            </div>
          </div>
        </div>

        {/* Documents */}
        <div className="bg-white rounded-2xl border border-[#D6E8DE] p-6 shadow-xs md:col-span-2 relative">
          <button onClick={() => onGoToStep(3)} className="absolute top-5 right-5 p-1.5 text-slate-400 hover:text-[#0F766E] rounded-lg hover:bg-[#ECFDF5] transition-colors cursor-pointer" title="Edit">
            <Edit3 className="w-4 h-4" />
          </button>
          <div className="flex items-center gap-2.5 mb-4 text-[#0F766E] font-bold text-xs uppercase tracking-wider">
            <FileCheck2 className="w-4 h-4" />
            <span>Uploaded Compliance Documents</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {docKeys.map((key) => {
              const doc = data.documents[key];
              return (
                <div key={key} className="flex items-center justify-between p-3 rounded-xl border border-[#D6E8DE] bg-[#FAFAF8]">
                  <div className="flex items-center gap-2.5">
                    <FileCheck2 className="w-4 h-4 text-[#0F766E]" />
                    <div>
                      <span className="text-xs font-bold text-[#0F172A] block">{DOC_LABELS[key] ?? key}</span>
                      <span className="text-[10px] text-slate-400 block">
                        {doc ? `${doc.fileName} (${doc.fileSize})` : 'Not uploaded'}
                      </span>
                    </div>
                  </div>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${doc?.status === 'completed' ? 'bg-[#ECFDF5] text-[#16A34A]' : 'bg-slate-200 text-slate-500'}`}>
                    {doc?.status === 'completed' ? 'Verified' : 'Missing'}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
