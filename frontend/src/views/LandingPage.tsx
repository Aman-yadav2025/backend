'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import {
  Recycle,
  Building2,
  Factory,
  ArrowRight,
  ShieldCheck,
  FileCheck2,
  CheckCircle,
  Sparkles,
  ClipboardList,
  Calculator,
  Scale,
  TrendingUp,
} from 'lucide-react';
import { MetricTonPricingModal } from '../components/pricing/MetricTonPricingModal';

export const LandingPage: React.FC = () => {
  const [isPricingModalOpen, setIsPricingModalOpen] = useState<boolean>(false);

  return (
    <div className="min-h-screen bg-[#FAFAF8] text-[#0F172A] font-sans selection:bg-[#ECFDF5] selection:text-[#0F766E] flex flex-col justify-between">
      {/* Navigation Header */}
      <nav className="sticky top-0 z-40 bg-white/90 backdrop-blur-md border-b border-[#D6E8DE] px-4 sm:px-8 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <Link href="/" className="flex items-center gap-3 group">
            <div className="w-10 h-10 rounded-xl bg-[#0F766E] flex items-center justify-center text-white shadow-md shadow-[#0F766E]/30 group-hover:bg-[#065F46] transition-colors">
              <Recycle className="w-6 h-6 animate-spin-slow" />
            </div>
            <div>
              <span className="font-extrabold text-xl text-[#0F172A] tracking-tight block">
                Punarvritt
              </span>
            </div>
          </Link>

          <div className="flex items-center gap-2 sm:gap-3">
            {/* Metric Ton Pricing Plan Button */}
            <button
              onClick={() => setIsPricingModalOpen(true)}
              className="text-xs sm:text-sm font-bold text-[#0F766E] bg-white hover:bg-[#ECFDF5] border border-[#0F766E]/30 hover:border-[#0F766E] px-3 sm:px-4 py-2.5 rounded-xl shadow-xs transition-all cursor-pointer flex items-center gap-1.5"
            >
              <Calculator className="w-4 h-4 text-[#0F766E]" />
              <span>Pricing Plans (MT)</span>
            </button>

            <Link
              href="/register/brand"
              className="text-xs sm:text-sm font-bold text-white bg-[#0F766E] hover:bg-[#065F46] px-3 sm:px-4 py-2.5 rounded-xl shadow-md shadow-[#0F766E]/20 transition-all cursor-pointer flex items-center gap-1.5"
            >
              <Building2 className="w-4 h-4" />
              <span>Brand Signup</span>
            </Link>

            <Link
              href="/register/recycler"
              className="text-xs sm:text-sm font-bold text-[#0F766E] bg-[#ECFDF5] hover:bg-emerald-100 border border-[#D6E8DE] px-3 sm:px-4 py-2.5 rounded-xl shadow-xs transition-all cursor-pointer flex items-center gap-1.5"
            >
              <Factory className="w-4 h-4" />
              <span>Recycler Signup</span>
            </Link>

            <div className="hidden md:flex items-center gap-2 ml-1 pl-2 border-l border-[#D6E8DE]">
              <Link
                href="/brand/login"
                className="text-xs font-semibold text-slate-700 hover:text-slate-900 px-2.5 py-2 rounded-lg hover:bg-slate-100 transition-colors"
              >
                Brand Login
              </Link>
              <Link
                href="/recycler/login"
                className="text-xs font-semibold text-slate-700 hover:text-slate-900 px-2.5 py-2 rounded-lg hover:bg-slate-100 transition-colors"
              >
                Recycler Login
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative overflow-hidden pt-12 sm:pt-20 pb-16 sm:pb-24 bg-gradient-to-b from-white via-[#FAFAF8] to-[#ECFDF5]/30 border-b border-[#D6E8DE]">
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[300px] bg-[#0F766E]/10 rounded-full blur-3xl pointer-events-none" />

        <div className="max-w-5xl mx-auto px-4 sm:px-6 text-center relative z-10">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-[#ECFDF5] border border-[#D6E8DE] text-[#0F766E] text-xs font-bold mb-6 shadow-xs">
            <ShieldCheck className="w-4 h-4 text-[#0F766E]" />
            <span>CPCB Verified Digital EPR Compliance Infrastructure</span>
          </div>

          <h1 className="text-3xl sm:text-5xl lg:text-6xl font-black text-[#0F172A] tracking-tight leading-[1.15]">
            India's Premium Network for <br className="hidden sm:inline" />
            <span className="bg-clip-text text-transparent bg-gradient-to-r from-[#0F766E] via-teal-700 to-[#065F46]">
              Plastic Recycling & EPR Compliance
            </span>
          </h1>

          <p className="mt-5 text-base sm:text-lg text-slate-600 max-w-2xl mx-auto font-normal leading-relaxed">
            Punarvritt connects Brand Owners, Producers & Importers (PIBOs) with certified Plastic Recyclers and Waste Aggregators to fulfill EPR obligations with end-to-end traceability.
          </p>

          {/* Primary CTA Buttons */}
          <div className="mt-8 sm:mt-10 flex flex-col sm:flex-row items-center justify-center gap-3 sm:gap-4 max-w-2xl mx-auto">
            <Link
              href="/register/brand"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2.5 px-6 py-3.5 bg-[#0F766E] text-white font-bold text-sm sm:text-base rounded-2xl shadow-lg shadow-[#0F766E]/25 hover:bg-[#065F46] active:scale-[0.99] transition-all hover:shadow-xl cursor-pointer"
            >
              <Building2 className="w-5 h-5 text-teal-200" />
              <span>Register as Brand</span>
              <ArrowRight className="w-5 h-5" />
            </Link>

            <Link
              href="/register/recycler"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2.5 px-6 py-3.5 bg-white text-[#0F766E] border-2 border-[#D6E8DE] hover:border-[#0F766E] font-bold text-sm sm:text-base rounded-2xl shadow-md hover:bg-[#ECFDF5]/50 active:scale-[0.99] transition-all cursor-pointer"
            >
              <Factory className="w-5 h-5 text-[#0F766E]" />
              <span>Register as Recycler</span>
              <ArrowRight className="w-5 h-5" />
            </Link>

            {/* Metric Ton Pricing Plan Button in Hero */}
            <button
              onClick={() => setIsPricingModalOpen(true)}
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3.5 bg-amber-500/10 hover:bg-amber-500/20 text-amber-900 border-2 border-amber-400/40 font-bold text-sm sm:text-base rounded-2xl shadow-xs active:scale-[0.99] transition-all cursor-pointer"
            >
              <Scale className="w-5 h-5 text-amber-600" />
              <span>Explore Metric Ton Pricing</span>
            </button>
          </div>

          {/* Login Links below CTA buttons */}
          <div className="mt-6 pt-4 flex flex-col sm:flex-row items-center justify-center gap-2 sm:gap-4 text-xs sm:text-sm text-slate-600">
            <span className="font-medium text-slate-500">Already registered?</span>
            <div className="flex items-center gap-3">
              <Link
                href="/brand/login"
                className="font-bold text-[#0F766E] hover:underline flex items-center gap-1"
              >
                <span>Brand Login</span>
                <ArrowRight className="w-3 h-3" />
              </Link>
              <span className="text-slate-300">•</span>
              <Link
                href="/recycler/login"
                className="font-bold text-[#0F766E] hover:underline flex items-center gap-1"
              >
                <span>Recycler Login</span>
                <ArrowRight className="w-3 h-3" />
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Stats Counter Section */}
      <section className="bg-white py-10 border-b border-[#D6E8DE]">
        <div className="max-w-6xl mx-auto px-4 sm:px-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6 text-center">
            <div className="p-4 rounded-2xl bg-[#FAFAF8] border border-[#D6E8DE]">
              <div className="text-2xl sm:text-3xl font-extrabold text-[#0F172A]">250,000+</div>
              <div className="text-xs font-semibold text-slate-500 mt-1">MT Plastic Traced</div>
            </div>
            <div className="p-4 rounded-2xl bg-[#FAFAF8] border border-[#D6E8DE]">
              <div className="text-2xl sm:text-3xl font-extrabold text-[#0F766E]">1,200+</div>
              <div className="text-xs font-semibold text-slate-500 mt-1">Registered Brands</div>
            </div>
            <div className="p-4 rounded-2xl bg-[#FAFAF8] border border-[#D6E8DE]">
              <div className="text-2xl sm:text-3xl font-extrabold text-[#0F172A]">850+</div>
              <div className="text-xs font-semibold text-slate-500 mt-1">Certified Recyclers</div>
            </div>
            <div className="p-4 rounded-2xl bg-[#FAFAF8] border border-[#D6E8DE]">
              <div className="text-2xl sm:text-3xl font-extrabold text-[#16A34A]">100%</div>
              <div className="text-xs font-semibold text-slate-500 mt-1">CPCB Audit Compliant</div>
            </div>
          </div>
        </div>
      </section>

      {/* Feature Highlights */}
      <section className="py-16 sm:py-20 bg-[#FAFAF8]">
        <div className="max-w-6xl mx-auto px-4 sm:px-6">
          <div className="text-center max-w-2xl mx-auto mb-12">
            <h2 className="text-2xl sm:text-3xl font-black text-[#0F172A] tracking-tight">
              Built for Complete Circular Economy Transparency
            </h2>
            <p className="mt-2 text-sm sm:text-base text-slate-600">
              Streamline plastic waste credit procurement, verify recycled content certificates, and automate CPCB portal filings.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6 sm:gap-8">
            <div className="bg-white rounded-3xl p-6 border border-[#D6E8DE] shadow-xs hover:border-[#0F766E]/40 transition-all">
              <div className="w-12 h-12 rounded-2xl bg-[#ECFDF5] text-[#0F766E] flex items-center justify-center mb-5">
                <Building2 className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-bold text-[#0F172A] mb-2">For Brand Owners & PIBOs</h3>
              <p className="text-xs sm:text-sm text-slate-600 leading-relaxed mb-4">
                Calculate annual EPR obligations across Category I, II, III, and IV plastic packaging. Purchase verified recycling credits directly from vetted recyclers.
              </p>
              <ul className="space-y-2 text-xs font-semibold text-[#0F172A]">
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-[#16A34A]" /> Real-time EPR credit balance
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-[#16A34A]" /> Automated CPCB filing export
                </li>
              </ul>
            </div>

            <div className="bg-white rounded-3xl p-6 border border-[#D6E8DE] shadow-xs hover:border-[#0F766E]/40 transition-all">
              <div className="w-12 h-12 rounded-2xl bg-[#ECFDF5] text-[#065F46] flex items-center justify-center mb-5">
                <Factory className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-bold text-[#0F172A] mb-2">For Recyclers & Aggregators</h3>
              <p className="text-xs sm:text-sm text-slate-600 leading-relaxed mb-4">
                Monetize processing capacity by issuing authenticated plastic recycling certificates. Connect directly with enterprise brand buyers nationwide.
              </p>
              <ul className="space-y-2 text-xs font-semibold text-[#0F172A]">
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-[#16A34A]" /> Instant credit marketplace listing
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-[#16A34A]" /> Digital batch verification
                </li>
              </ul>
            </div>

            <div className="bg-white rounded-3xl p-6 border border-[#D6E8DE] shadow-xs hover:border-[#0F766E]/40 transition-all">
              <div className="w-12 h-12 rounded-2xl bg-teal-50 text-[#0F766E] flex items-center justify-center mb-5">
                <FileCheck2 className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-bold text-[#0F172A] mb-2">Traceability & Audit Trail</h3>
              <p className="text-xs sm:text-sm text-slate-600 leading-relaxed mb-4">
                Every metric ton logged on Punarvritt includes GST invoice verification, weighbridge slips, and material origin validation for flawless regulatory compliance.
              </p>
              <ul className="space-y-2 text-xs font-semibold text-[#0F172A]">
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-[#16A34A]" /> End-to-end chain of custody
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-[#16A34A]" /> Tamper-evident certificate IDs
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Metric Ton Pricing Callout Section */}
      <section className="py-12 bg-[#0F172A] text-white relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-[#0F766E]/20 rounded-full blur-3xl pointer-events-none" />
        <div className="max-w-6xl mx-auto px-4 sm:px-6 relative z-10 flex flex-col md:flex-row items-center justify-between gap-8">
          <div className="space-y-3 text-center md:text-left">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#ECFDF5]/10 border border-[#ECFDF5]/20 text-teal-300 text-xs font-bold">
              <Scale className="w-3.5 h-3.5" />
              <span>Volume-Based Transparent Pricing</span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
              Pay Only For The Metric Tons You Process
            </h2>
            <p className="text-xs sm:text-sm text-slate-300 max-w-xl">
              Whether you are a Brand managing 25 MT or a Recycler processing 10,000+ MT annually, our tiered metric-ton pricing ensures complete cost predictability with no hidden fees.
            </p>
          </div>

          <div className="shrink-0 w-full md:w-auto text-center">
            <button
              onClick={() => setIsPricingModalOpen(true)}
              className="w-full sm:w-auto px-8 py-4 bg-[#0F766E] hover:bg-[#065F46] text-white font-extrabold text-sm sm:text-base rounded-2xl shadow-xl shadow-[#0F766E]/40 active:scale-[0.99] transition-all flex items-center justify-center gap-2.5 mx-auto"
            >
              <Calculator className="w-5 h-5 text-teal-200" />
              <span>Calculate Your Price by Metric Tons</span>
              <ArrowRight className="w-5 h-5" />
            </button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-[#0F172A] text-slate-400 py-8 px-4 text-xs border-t border-slate-800">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-white font-bold">
            <Recycle className="w-4 h-4 text-[#0F766E]" />
            <span>Punarvritt Circular Economy Solutions</span>
          </div>
          <p>© 2026 Punarvritt. All rights reserved. CPCB Certified Platform.</p>
        </div>
      </footer>

      {/* Metric Ton Pricing Modal */}
      <MetricTonPricingModal
        isOpen={isPricingModalOpen}
        onClose={() => setIsPricingModalOpen(false)}
      />
    </div>
  );
};

