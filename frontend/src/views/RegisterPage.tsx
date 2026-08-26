'use client';

import React, { Suspense } from 'react';
import { RegistrationWizard } from '../components/registration/RegistrationWizard';
import { useRouter, useSearchParams } from 'next/navigation';

interface RegisterPageProps {
  type?: 'brand' | 'recycler';
}

function RegisterContent({ type }: RegisterPageProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const typeParam = type || (searchParams.get('type') as 'brand' | 'recycler' | null);

  const handleClose = () => {
    router.push('/');
  };

  return (
    <RegistrationWizard
      isOpen={true}
      onClose={handleClose}
      initialType={typeParam || undefined}
    />
  );
}

export const RegisterPage: React.FC<RegisterPageProps> = ({ type }) => {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#FAFAF8] flex items-center justify-center font-sans text-slate-500">Loading registration...</div>}>
      <RegisterContent type={type} />
    </Suspense>
  );
};

