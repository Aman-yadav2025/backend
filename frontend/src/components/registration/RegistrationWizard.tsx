'use client';

import React from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  ArrowLeft, ArrowRight, ShieldCheck, Loader2, AlertCircle,
  Eye, EyeOff, Mail, Lock,
} from 'lucide-react';
import Link from 'next/link';
import { useRegistration, TOTAL_STEPS } from '../../hooks/useRegistration';
import { WizardHeader } from './WizardHeader';
import { Stepper } from './Stepper';
import { RegistrationCard } from './RegistrationCard';
import { MaterialCard } from './MaterialCard';
import { CompanyForm } from './CompanyForm';
import { UploadCard } from './UploadCard';
import { CapacityCard } from './CapacityCard';
import { PricingCard } from './PricingCard';
import { SummaryCard } from './SummaryCard';
import { SuccessModal } from './SuccessModal';
import { PrimaryButton } from './PrimaryButton';
import { SecondaryButton } from './SecondaryButton';
import { getRequiredDocuments } from '../../data/pricing';
import { useState, useEffect } from 'react';

interface RegistrationWizardProps {
  isOpen: boolean;
  onClose: () => void;
  initialType?: 'brand' | 'recycler';
}

const STEP_TITLES = [
  'Create Your Account',                  // 1
  'Choose Registration Type & Role',      // 2
  'Company Information & Identification', // 3
  'Upload Required Compliance Documents', // 4
  'Choose Primary Material Category',      // 5
  'Select Annual Processing Capacity',     // 6
  'Select Subscription Plan',              // 7
  'Registration Summary & Submission',     // 8
];

export const RegistrationWizard: React.FC<RegistrationWizardProps> = ({
  isOpen,
  onClose,
  initialType,
}) => {
  const {
    step, data, errors, saveToast, isSubmitted,
    isPaymentLoading, paymentError, paymentResult,
    isAuthenticated,
    accountEmail, accountPassword, accountConfirm,
    accountLoading, accountError,
    setAccountEmail, setAccountPassword, setAccountConfirm,
    appliedPromoCode, promoDiscountAmount, promoFinalAmount, promoOriginalAmount,
    applyPromoCode, removePromoCode,
    setRegistrationType, setBrandSubRole, setMaterialCategory, updateCompanyInfo,
    setCapacityTier, setPlasticCapacityTier, setMetalCapacityTier, setSubscriptionPlan,
    uploadDocument, removeDocument,
    nextStep, prevStep, goToStep,
    saveProgress, submitRegistration, resetWizard,
  } = useRegistration();

  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  useEffect(() => {
    if (initialType && data.registrationType !== initialType) {
      setRegistrationType(initialType);
    }
  }, [initialType, data.registrationType, setRegistrationType]);

  if (!isOpen) return null;

  // Steps 1 is not shown in the stepper (it's pre-wizard auth)
  // Display stepper from step 2 onward; steps 2–8 map to stepper positions 1–7
  const stepperStep = Math.max(step - 1, 1);
  const stepperTotal = TOTAL_STEPS - 1; // 7 visible steps

  return (
    <div className="min-h-screen bg-[#FAFAF8] text-[#0F172A] font-sans flex flex-col justify-between selection:bg-[#ECFDF5] selection:text-[#0F766E]">
      <div className="flex-1 flex flex-col max-w-7xl mx-auto w-full px-2 sm:px-6 lg:px-8 py-4 sm:py-8">
        <div className="bg-white rounded-2xl sm:rounded-3xl border border-[#D6E8DE] shadow-xl flex flex-col overflow-hidden min-h-[calc(100vh-4rem)]">
          <WizardHeader
            currentStep={stepperStep}
            totalSteps={stepperTotal}
            stepTitle={STEP_TITLES[step - 1]}
            onSaveProgress={saveProgress}
            onClose={onClose}
            saveToast={saveToast}
          />

        {/* Only show stepper from step 2 onward */}
        {step > 1 && (
          <Stepper currentStep={stepperStep} totalSteps={stepperTotal} onStepClick={(s) => goToStep(s + 1)} />
        )}

        <div className="flex-1 overflow-y-auto p-4 sm:p-8">
          <AnimatePresence mode="wait">
            <motion.div
              key={step}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.25 }}
              className="max-w-5xl mx-auto"
            >
              <div className="mb-6 sm:mb-8 text-center sm:text-left">
                {step > 1 && (
                  <span className="text-xs font-bold uppercase tracking-widest text-[#0F766E] block mb-1">
                    Step {step - 1} of {TOTAL_STEPS - 1}
                  </span>
                )}
                <h2 className="text-2xl sm:text-3xl font-black text-[#0F172A] tracking-tight">
                  {STEP_TITLES[step - 1]}
                </h2>
              </div>

              {/* ── STEP 1: Create Account ─────────────────────────────────── */}
              {step === 1 && (
                <div className="max-w-md mx-auto">
                  <p className="text-sm text-slate-500 mb-6 text-center">
                    Create a secure account to save your progress and complete your registration.
                  </p>

                  {accountError && (
                    <div className="flex items-start gap-2.5 p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs font-semibold mb-5">
                      <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                      <span>{accountError}</span>
                    </div>
                  )}

                  <div className="space-y-4">
                    {/* Email */}
                    <div>
                      <label className="block text-xs font-bold text-slate-700 mb-1.5">
                        Email Address <span className="text-red-500">*</span>
                      </label>
                      <div className="relative">
                        <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                        <input
                          type="email"
                          value={accountEmail}
                          onChange={(e) => setAccountEmail(e.target.value)}
                          placeholder="company@example.com"
                          autoComplete="email"
                          className={`w-full h-11 pl-10 pr-4 text-sm rounded-xl border bg-white outline-none transition-colors ${
                            errors.accountEmail
                              ? 'border-red-300 focus:border-red-400'
                              : 'border-[#D6E8DE] focus:border-[#0F766E]'
                          }`}
                        />
                      </div>
                      {errors.accountEmail && (
                        <p className="text-xs text-red-600 mt-1 font-medium">{errors.accountEmail}</p>
                      )}
                    </div>

                    {/* Password */}
                    <div>
                      <label className="block text-xs font-bold text-slate-700 mb-1.5">
                        Password <span className="text-red-500">*</span>
                        <span className="font-normal text-slate-400 ml-1">(min. 8 characters)</span>
                      </label>
                      <div className="relative">
                        <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                        <input
                          type={showPassword ? 'text' : 'password'}
                          value={accountPassword}
                          onChange={(e) => setAccountPassword(e.target.value)}
                          placeholder="••••••••"
                          autoComplete="new-password"
                          className={`w-full h-11 pl-10 pr-11 text-sm rounded-xl border bg-white outline-none transition-colors ${
                            errors.accountPassword
                              ? 'border-red-300 focus:border-red-400'
                              : 'border-[#D6E8DE] focus:border-[#0F766E]'
                          }`}
                        />
                        <button
                          type="button"
                          onClick={() => setShowPassword((v) => !v)}
                          className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 cursor-pointer"
                        >
                          {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        </button>
                      </div>
                      {errors.accountPassword && (
                        <p className="text-xs text-red-600 mt-1 font-medium">{errors.accountPassword}</p>
                      )}
                    </div>

                    {/* Confirm Password */}
                    <div>
                      <label className="block text-xs font-bold text-slate-700 mb-1.5">
                        Confirm Password <span className="text-red-500">*</span>
                      </label>
                      <div className="relative">
                        <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                        <input
                          type={showConfirm ? 'text' : 'password'}
                          value={accountConfirm}
                          onChange={(e) => setAccountConfirm(e.target.value)}
                          placeholder="••••••••"
                          autoComplete="new-password"
                          className={`w-full h-11 pl-10 pr-11 text-sm rounded-xl border bg-white outline-none transition-colors ${
                            errors.accountConfirm
                              ? 'border-red-300 focus:border-red-400'
                              : 'border-[#D6E8DE] focus:border-[#0F766E]'
                          }`}
                        />
                        <button
                          type="button"
                          onClick={() => setShowConfirm((v) => !v)}
                          className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 cursor-pointer"
                        >
                          {showConfirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        </button>
                      </div>
                      {errors.accountConfirm && (
                        <p className="text-xs text-red-600 mt-1 font-medium">{errors.accountConfirm}</p>
                      )}
                    </div>
                  </div>

                  {/* Already have an account */}
                  <p className="text-xs text-slate-500 mt-6 text-center">
                    Already have an account?{' '}
                    <Link
                      href={initialType === 'recycler' ? '/recycler/login' : '/brand/login'}
                      className="font-bold text-[#0F766E] hover:underline"
                    >
                      Sign in here
                    </Link>
                  </p>
                </div>
              )}

              {/* ── STEP 2: Registration Type & Role ──────────────────────── */}
              {step === 2 && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 sm:gap-8">
                  <RegistrationCard
                    type="brand"
                    selected={data.registrationType === 'brand'}
                    onSelect={setRegistrationType}
                    onContinue={nextStep}
                    brandSubRole={data.brandSubRole}
                    onSelectBrandSubRole={setBrandSubRole}
                  />
                  <RegistrationCard
                    type="recycler"
                    selected={data.registrationType === 'recycler'}
                    onSelect={setRegistrationType}
                    onContinue={nextStep}
                  />
                </div>
              )}

              {/* ── STEP 3: Company Info ──────────────────────────────────── */}
              {step === 3 && (
                <CompanyForm
                  companyInfo={data.companyInfo}
                  onChange={updateCompanyInfo}
                  errors={errors}
                />
              )}

              {/* ── STEP 4: Document Upload ───────────────────────────────── */}
              {step === 4 && (
                <div className="space-y-4">
                  {errors.documents && (
                    <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs font-bold">
                      {errors.documents}
                    </div>
                  )}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6">
                    {getRequiredDocuments(data.registrationType).map((doc) => (
                      <UploadCard
                        key={doc.id}
                        docType={doc.id}
                        title={doc.title}
                        description={doc.description}
                        required={doc.required}
                        allowedTypes={doc.allowedTypes}
                        document={data.documents[doc.id] || null}
                        onUpload={uploadDocument}
                        onRemove={removeDocument}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* ── STEP 5: Material Category ─────────────────────────────── */}
              {step === 5 && (
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-5 max-w-5xl mx-auto">
                  <MaterialCard
                    material="plastic"
                    selected={data.materialCategory === 'plastic'}
                    onSelect={setMaterialCategory}
                  />
                  <MaterialCard
                    material="metal"
                    selected={data.materialCategory === 'metal'}
                    onSelect={setMaterialCategory}
                  />
                  <MaterialCard
                    material="plastic_and_metal"
                    selected={data.materialCategory === 'plastic_and_metal'}
                    onSelect={setMaterialCategory}
                  />
                </div>
              )}

              {/* ── STEP 6: Capacity Tier ─────────────────────────────────── */}
              {step === 6 && (
                <CapacityCard
                  registrationType={data.registrationType}
                  materialCategory={data.materialCategory}
                  selectedTier={data.capacityTier}
                  onSelect={setCapacityTier}
                  plasticTier={data.plasticCapacityTier}
                  metalTier={data.metalCapacityTier}
                  onSelectPlasticTier={setPlasticCapacityTier}
                  onSelectMetalTier={setMetalCapacityTier}
                />
              )}

              {/* ── STEP 7: Subscription Plan ────────────────────────────── */}
              {step === 7 && (
                <PricingCard
                  capacityTier={data.capacityTier}
                  selectedPlan={data.subscriptionPlan}
                  onSelectPlan={setSubscriptionPlan}
                />
              )}

              {/* ── STEP 8: Summary + Payment ─────────────────────────────── */}
              {step === 8 && (
                <SummaryCard
                  data={data}
                  onGoToStep={(s) => goToStep(s + 1)}
                  appliedPromoCode={appliedPromoCode}
                  promoDiscountAmount={promoDiscountAmount}
                  promoFinalAmount={promoFinalAmount}
                  promoOriginalAmount={promoOriginalAmount}
                  onApplyPromo={applyPromoCode}
                  onRemovePromo={removePromoCode}
                />
              )}
            </motion.div>
          </AnimatePresence>
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 z-20 border-t border-[#D6E8DE] bg-white px-4 sm:px-8 py-3.5 sm:py-4 flex flex-col gap-2 shadow-md sm:shadow-none">
          {step === 8 && paymentError && (
            <div className="flex items-start gap-2.5 p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs font-semibold">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{paymentError}</span>
            </div>
          )}

          <div className="flex items-center justify-between gap-3">
            <div>
              {step > (isAuthenticated ? 2 : 1) ? (
                <SecondaryButton
                  onClick={prevStep}
                  size="md"
                  icon={<ArrowLeft className="w-4 h-4" />}
                  disabled={isPaymentLoading}
                >
                  Previous
                </SecondaryButton>
              ) : (
                <SecondaryButton onClick={onClose} size="md">
                  Cancel
                </SecondaryButton>
              )}
            </div>

            <div>
              {step < TOTAL_STEPS ? (
                <PrimaryButton
                  onClick={nextStep}
                  size="md"
                  disabled={accountLoading}
                  icon={
                    accountLoading
                      ? <Loader2 className="w-4 h-4 animate-spin" />
                      : <ArrowRight className="w-4 h-4" />
                  }
                >
                  {step === 1 ? (accountLoading ? 'Creating Account…' : 'Create Account') : 'Next Step'}
                </PrimaryButton>
              ) : (
                <PrimaryButton
                  onClick={submitRegistration}
                  size="lg"
                  disabled={isPaymentLoading}
                  icon={
                    isPaymentLoading
                      ? <Loader2 className="w-5 h-5 animate-spin" />
                      : <ShieldCheck className="w-5 h-5" />
                  }
                  className="bg-[#16A34A] hover:bg-[#15803D] disabled:opacity-70"
                >
                  {isPaymentLoading ? 'Processing…' : 'Pay & Register'}
                </PrimaryButton>
              )}
            </div>
          </div>
          </div>
        </div>
      </div>

      {isSubmitted && (
        <SuccessModal
          data={data}
          paymentResult={paymentResult}
          onReset={() => resetWizard()}
          onClose={() => onClose()}
        />
      )}
    </div>
  );
};
