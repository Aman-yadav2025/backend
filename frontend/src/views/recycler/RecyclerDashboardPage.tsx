'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Recycle, Factory, FileCheck2, TrendingUp, Download,
  LogOut, CheckCircle, Clock, ShieldCheck, AlertTriangle,
  CreditCard, RefreshCw, PackageCheck,
} from 'lucide-react';
import { createClient } from '@/utils/supabase/client';

interface CompanyRow {
  id: string;
  name: string;
  email: string;
  gst_number: string;
  capacity_tier: string;
  subscription_plan: string;
  status: string;
  amount_paid: number | null;
  discount_amount: number | null;
  promo_code_used: string | null;
  razorpay_payment_id: string | null;
  created_at: string;
}

interface PaymentRow {
  id: string;
  razorpay_order_id: string;
  razorpay_payment_id: string | null;
  amount: number;
  original_amount: number | null;
  discount_amount: number;
  promo_code: string | null;
  status: string;
  created_at: string;
}

function formatPaise(paise: number | null): string {
  if (!paise) return '—';
  return new Intl.NumberFormat('en-IN', {
    style: 'currency', currency: 'INR', maximumFractionDigits: 0,
  }).format(paise / 100);
}

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  draft:                { label: 'Draft', color: 'bg-slate-100 text-slate-600' },
  pending_verification: { label: 'Pending Verification', color: 'bg-amber-100 text-amber-700' },
  approved:             { label: 'Approved', color: 'bg-emerald-100 text-emerald-700' },
  rejected:             { label: 'Rejected', color: 'bg-red-100 text-red-700' },
};

export const RecyclerDashboardPage: React.FC = () => {
  const router = useRouter();
  const [company, setCompany] = useState<CompanyRow | null>(null);
  const [payments, setPayments] = useState<PaymentRow[]>([]);
  const [userEmail, setUserEmail] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      const supabase = createClient();
      const { data: { user } } = await supabase.auth.getUser();
      const isTestMode = typeof window !== 'undefined' && localStorage.getItem('punarvritt_test_mode') === 'true';

      if (!user && !isTestMode) { router.push('/recycler/login'); return; }
      setUserEmail(user?.email ?? 'test@test.com');

      let co: CompanyRow | null = null;
      let coErr: any = null;
      let pays: PaymentRow[] | null = null;

      if (user) {
        const resCo = await supabase.from('companies').select('*').eq('profile_id', user.id).single();
        co = resCo.data;
        coErr = resCo.error;
        if (co) {
          const resPays = await supabase.from('payments').select('*').eq('company_id', co.id).order('created_at', { ascending: false });
          pays = resPays.data;
        }
      } else if (isTestMode) {
        co = {
          id: 'test-co', name: 'Test Recycler Corp', email: 'test@recycler.com', gst_number: '22AAAAA0000A1Z5',
          capacity_tier: 'tier2', subscription_plan: 'growth', status: 'approved', amount_paid: 500000,
          discount_amount: null, promo_code_used: null, razorpay_payment_id: 'pay_test123', created_at: new Date().toISOString()
        } as any;
        pays = [{
          id: 'test-pay', razorpay_order_id: 'order_test123', razorpay_payment_id: 'pay_test123',
          amount: 500000, original_amount: 500000, discount_amount: 0, promo_code: null, status: 'captured', created_at: new Date().toISOString()
        } as any];
      }

      if (coErr && coErr.code !== 'PGRST116') {
        setError('Failed to load company data.');
        setLoading(false);
        return;
      }

      setCompany(co ?? null);
      setPayments(pays ?? []);

      setLoading(false);
    };
    load();
  }, [router]);

  const handleSignOut = async () => {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push('/recycler/login');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <RefreshCw className="w-6 h-6 animate-spin text-emerald-600" />
      </div>
    );
  }

  const statusInfo = company ? (STATUS_MAP[company.status] ?? STATUS_MAP.draft) : null;
  const planLabel = company?.subscription_plan
    ? company.subscription_plan.charAt(0).toUpperCase() + company.subscription_plan.slice(1)
    : '—';

  return (
    <div className="min-h-screen bg-slate-50 font-sans">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-30 px-4 sm:px-8 py-3.5">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/" className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-xl bg-emerald-600 flex items-center justify-center text-white shadow-sm">
                <Recycle className="w-5 h-5" />
              </div>
              <span className="font-extrabold text-lg text-slate-900 tracking-tight">Punarvritt</span>
            </Link>
            <span className="hidden sm:inline-block text-slate-300">|</span>
            <span className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-800 text-xs font-semibold border border-emerald-200">
              <Factory className="w-3.5 h-3.5" /> Recycler Portal
            </span>
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden md:block text-xs text-slate-500">{userEmail}</span>
            <button
              onClick={handleSignOut}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-colors cursor-pointer"
            >
              <LogOut className="w-3.5 h-3.5" /> Sign Out
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-8 py-8 space-y-6">

        {error && (
          <div className="p-4 rounded-2xl bg-red-50 border border-red-200 text-red-700 text-sm font-semibold flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" /> {error}
          </div>
        )}

        {!company && !error && (
          <div className="bg-white rounded-2xl border border-slate-200 p-10 text-center shadow-xs">
            <div className="w-14 h-14 rounded-2xl bg-amber-100 text-amber-600 flex items-center justify-center mx-auto mb-4">
              <AlertTriangle className="w-7 h-7" />
            </div>
            <h2 className="text-xl font-bold text-slate-900 mb-2">Registration not found</h2>
            <p className="text-sm text-slate-500 mb-5">
              Complete the signup wizard to register your recycling facility.
            </p>
            <Link
              href="/recycler/signup"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-[#0F766E] text-white font-bold text-sm hover:bg-[#065F46] transition-colors"
            >
              Complete Registration
            </Link>
          </div>
        )}

        {company && (
          <>
            {/* Welcome card */}
            <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs">
              <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                <div>
                  <div className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold mb-2 ${statusInfo?.color}`}>
                    <CheckCircle className="w-3.5 h-3.5" />
                    {statusInfo?.label} · {planLabel} Plan
                  </div>
                  <h1 className="text-2xl font-extrabold text-slate-900">{company.name}</h1>
                  <p className="text-xs text-slate-500 mt-1">
                    GST: <span className="font-mono font-bold">{company.gst_number}</span>
                    {' '}· Capacity: <span className="font-bold uppercase">{company.capacity_tier}</span>
                    {' '}· Registered: {new Date(company.created_at).toLocaleDateString('en-IN')}
                  </p>
                </div>
                {company.status === 'approved' && (
                  <button className="flex items-center gap-2 px-4 py-2 rounded-xl border border-slate-200 text-xs font-bold text-slate-700 hover:bg-slate-50 cursor-pointer">
                    <Download className="w-3.5 h-3.5" /> Weighbridge Logs
                  </button>
                )}
              </div>
            </div>

            {company.status === 'pending_verification' && (
              <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 flex items-start gap-3">
                <Clock className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-bold text-amber-800">Facility Verification in Progress</p>
                  <p className="text-xs text-amber-700 mt-0.5">
                    Our team is verifying your recycler certifications and pollution certificates.
                    This typically takes 3–5 business days.
                  </p>
                </div>
              </div>
            )}

            {/* Stats */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
              {[
                {
                  label: 'Subscription Plan',
                  value: planLabel,
                  sub: company.capacity_tier.toUpperCase() + ' Tier',
                  icon: <PackageCheck className="w-4 h-4 text-emerald-600" />,
                },
                {
                  label: 'Amount Paid',
                  value: formatPaise(company.amount_paid),
                  sub: company.promo_code_used ? `Promo: ${company.promo_code_used}` : 'No promo applied',
                  icon: <CreditCard className="w-4 h-4 text-blue-600" />,
                },
                {
                  label: 'Payment Status',
                  value: payments[0]?.status === 'captured' ? 'Captured' : payments[0]?.status ?? '—',
                  sub: payments[0]?.razorpay_payment_id?.slice(0, 16) ?? '—',
                  icon: <ShieldCheck className="w-4 h-4 text-teal-600" />,
                },
                {
                  label: 'Account Status',
                  value: statusInfo?.label ?? '—',
                  sub: 'Facility registration',
                  icon: <TrendingUp className="w-4 h-4 text-emerald-600" />,
                },
              ].map((s) => (
                <div key={s.label} className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs">
                  <div className="flex items-center justify-between text-slate-500 mb-2">
                    <span className="text-xs font-semibold">{s.label}</span>
                    {s.icon}
                  </div>
                  <div className="text-xl font-black text-slate-900">{s.value}</div>
                  <div className="text-[11px] text-slate-500 mt-1">{s.sub}</div>
                </div>
              ))}
            </div>

            {/* Payment history */}
            {payments.length > 0 && (
              <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs">
                <h2 className="text-base font-bold text-slate-900 mb-4 flex items-center gap-2">
                  <FileCheck2 className="w-4 h-4 text-[#0F766E]" /> Payment History
                </h2>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left border-collapse">
                    <thead>
                      <tr className="border-b border-slate-100 text-slate-500 font-bold uppercase tracking-wide text-[10px]">
                        <th className="py-2.5 px-3">Payment ID</th>
                        <th className="py-2.5 px-3">Amount Paid</th>
                        <th className="py-2.5 px-3">Discount</th>
                        <th className="py-2.5 px-3">Promo</th>
                        <th className="py-2.5 px-3">Status</th>
                        <th className="py-2.5 px-3">Date</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-50">
                      {payments.map((p) => (
                        <tr key={p.id} className="hover:bg-slate-50">
                          <td className="py-3 px-3 font-mono text-[#0F766E] font-bold text-[10px]">
                            {p.razorpay_payment_id ?? '—'}
                          </td>
                          <td className="py-3 px-3 font-bold">{formatPaise(p.amount)}</td>
                          <td className="py-3 px-3 text-emerald-600 font-semibold">
                            {p.discount_amount ? `− ${formatPaise(p.discount_amount)}` : '—'}
                          </td>
                          <td className="py-3 px-3">
                            {p.promo_code
                              ? <span className="font-mono font-bold text-[#0F766E] bg-[#ECFDF5] px-1.5 py-0.5 rounded text-[10px]">{p.promo_code}</span>
                              : '—'}
                          </td>
                          <td className="py-3 px-3">
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${p.status === 'captured' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                              {p.status}
                            </span>
                          </td>
                          <td className="py-3 px-3 text-slate-500">
                            {new Date(p.created_at).toLocaleDateString('en-IN')}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
};
