'use client';

import React, { useState } from 'react';
import { AuthLayout } from '../../components/auth/AuthLayout';
import { Card } from '../../components/ui/Card';
import { Input } from '../../components/ui/Input';
import { PasswordInput } from '../../components/auth/PasswordInput';
import { Checkbox } from '../../components/ui/Checkbox';
import { Button } from '../../components/ui/Button';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Factory, LogIn, ArrowLeft } from 'lucide-react';
import { createClient } from '@/utils/supabase/client';

export const RecyclerLoginPage: React.FC = () => {
  const router = useRouter();

  const [formData, setFormData] = useState({ email: '', password: '', rememberMe: false });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(false);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type, checked } = e.target;
    setFormData((prev) => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
    if (errors[name]) setErrors((prev) => { const c = { ...prev }; delete c[name]; return c; });
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!formData.email.trim()) errs.email = 'Email address is required';
    else if (!/\S+@\S+\.\S+/.test(formData.email)) errs.email = 'Please enter a valid email address';
    if (!formData.password) errs.password = 'Password is required';
    if (Object.keys(errs).length) { setErrors(errs); return; }

    setErrors({});
    setIsLoading(true);
    try {
      if (formData.email.trim().toLowerCase() === 'test@test.com') {
        localStorage.setItem('punarvritt_test_mode', 'true');
        router.push('/recycler/dashboard');
        return;
      }

      const supabase = createClient();
      const { error } = await supabase.auth.signInWithPassword({
        email: formData.email.trim().toLowerCase(),
        password: formData.password,
      });
      if (error) { setErrors({ form: 'Invalid email or password. Please try again.' }); return; }
      router.push('/recycler/dashboard');
      router.refresh();
    } catch {
      setErrors({ form: 'Something went wrong. Please try again.' });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthLayout
      title="Recycler & Aggregator Login"
      subtitle="Manage your processed material batches, credit listings, and buyer certificate requests."
      userType="recycler"
    >
      <div className="max-w-md mx-auto w-full">
        <Card variant="default" padding="lg" className="shadow-md">
          <div className="flex items-center gap-3 mb-6 pb-4 border-b border-slate-100">
            <div className="w-10 h-10 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center">
              <Factory className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900">Recycler Login</h2>
              <p className="text-xs text-slate-500">Sign in to facility management portal</p>
            </div>
          </div>

          <form onSubmit={handleLogin} className="space-y-5">
            <Input
              label="Facility Email Address"
              name="email"
              type="email"
              placeholder="facility@recycler.com"
              value={formData.email}
              onChange={handleInputChange}
              error={errors.email}
              requiredStar
            />

            <div>
              <div className="flex items-center justify-between mb-1">
                <span />
                <a
                  href="#"
                  onClick={async (e) => {
                    e.preventDefault();
                    if (!formData.email) { alert('Enter your email above first.'); return; }
                    const supabase = createClient();
                    await supabase.auth.resetPasswordForEmail(formData.email.trim().toLowerCase());
                    alert('Password reset link sent to your facility email.');
                  }}
                  className="text-xs font-semibold text-emerald-700 hover:text-emerald-800 hover:underline"
                >
                  Forgot Password?
                </a>
              </div>
              <PasswordInput
                label="Password"
                name="password"
                placeholder="Enter facility password"
                value={formData.password}
                onChange={handleInputChange}
                error={errors.password}
                requiredStar
              />
            </div>

            <div className="pt-1">
              <Checkbox
                id="rememberMe"
                name="rememberMe"
                checked={formData.rememberMe}
                onChange={handleInputChange}
                label="Remember this facility terminal"
              />
            </div>

            {errors.form && (
              <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs font-semibold">
                {errors.form}
              </div>
            )}

            <div className="space-y-3 pt-3">
              <Button
                type="submit"
                variant="primary"
                size="lg"
                fullWidth
                icon={<LogIn className="w-4 h-4" />}
                iconPosition="right"
                disabled={isLoading}
              >
                {isLoading ? 'Signing in…' : 'Login to Recycler Dashboard'}
              </Button>
              <Button
                type="button"
                variant="outline"
                size="md"
                fullWidth
                icon={<ArrowLeft className="w-4 h-4" />}
                iconPosition="left"
                onClick={() => router.push('/')}
              >
                Back to Home
              </Button>
            </div>
          </form>

          <div className="mt-6 pt-5 border-t border-slate-100 text-center text-xs text-slate-600">
            Don&apos;t have an account?{' '}
            <Link href="/recycler/signup" className="font-bold text-emerald-700 hover:underline ml-1">
              Create Recycler Account
            </Link>
          </div>
        </Card>
      </div>
    </AuthLayout>
  );
};
