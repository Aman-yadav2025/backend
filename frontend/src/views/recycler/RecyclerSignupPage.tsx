'use client';

import React from 'react';
import { RegistrationWizard } from '../../components/registration/RegistrationWizard';
import { useRouter } from 'next/navigation';

export const RecyclerSignupPage: React.FC = () => {
  const router = useRouter();

  return (
    <RegistrationWizard
      isOpen={true}
      onClose={() => router.push('/')}
      initialType="recycler"
    />
  );
};
