'use client';

import React from 'react';
import Link from 'next/link';
import { Recycle, ArrowLeft, ShieldCheck, Leaf } from 'lucide-react';

interface AuthLayoutProps {
  children: React.ReactNode;
  title: string;
  subtitle?: string;
  userType?: 'brand' | 'recycler';
  showBackHome?: boolean;
}

export const AuthLayout: React.FC<AuthLayoutProps> = ({
  children,
  title,
  subtitle,
  userType,
  showBackHome = true,
}) => {
  return (
    <div className="min-h-screen bg-slate-50/80 flex flex-col justify-between font-sans selection:bg-emerald-100 selection:text-emerald-900">
      {/* Top Header Navigation */}
      <header className="sticky top-0 z-40 bg-white/80 backdrop-blur-md border-b border-slate-200/80 px-4 sm:px-8 py-3.5">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="w-9 h-9 rounded-xl bg-emerald-600 flex items-center justify-center text-white shadow-sm shadow-emerald-600/30 group-hover:bg-emerald-700 transition-colors">
              <Recycle className="w-5 h-5" />
            </div>
            <div className="flex flex-col">
              <span className="font-bold text-lg text-slate-900 tracking-tight leading-none group-hover:text-emerald-700 transition-colors">
                Punarvritt
              </span>
              <span className="text-[10px] font-semibold tracking-widest uppercase text-emerald-600">
                EPR & Recycled Plastic Network
              </span>
            </div>
          </Link>

          <div className="flex items-center gap-3">
            {userType && (
              <span className={`px-2.5 py-1 rounded-full text-xs font-semibold capitalize border ${
                userType === 'brand' 
                  ? 'bg-blue-50 text-blue-700 border-blue-200' 
                  : 'bg-emerald-50 text-emerald-800 border-emerald-200'
              }`}>
                {userType === 'brand' ? 'Brand Access' : 'Recycler Access'}
              </span>
            )}

            {showBackHome && (
              <Link
                href="/"
                className="hidden sm:inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-slate-900 px-3 py-1.5 rounded-lg hover:bg-slate-100 transition-colors"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                Back to Home
              </Link>
            )}
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-5xl w-full mx-auto px-4 sm:px-6 py-8 sm:py-12 flex flex-col justify-center">
        <div className="text-center max-w-xl mx-auto mb-8 sm:mb-10">
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            {title}
          </h1>
          {subtitle && (
            <p className="mt-2 text-sm sm:text-base text-slate-600 font-normal">
              {subtitle}
            </p>
          )}
        </div>

        {children}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200/80 py-6 px-4 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-slate-600">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <span>Encrypted 256-bit EPR Compliance Infrastructure</span>
          </div>
          <div className="flex items-center gap-4 text-slate-500">
            <Link href="/" className="hover:text-slate-800 transition-colors">Privacy Policy</Link>
            <span>•</span>
            <Link href="/" className="hover:text-slate-800 transition-colors">Terms of Service</Link>
            <span>•</span>
            <Link href="/" className="hover:text-slate-800 transition-colors">Central Pollution Control Board (CPCB) Verified</Link>
          </div>
        </div>
      </footer>
    </div>
  );
};
