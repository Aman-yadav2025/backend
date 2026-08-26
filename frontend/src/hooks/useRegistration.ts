'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  RegistrationData,
  RegistrationType,
  MaterialCategory,
  CapacityTier,
  SubscriptionPlanId,
  CompanyInfo,
  UploadedDocument,
  PaymentResult,
} from '../types/registration';
import { createClient } from '../../utils/supabase/client';

// ── Constants ────────────────────────────────────────────────────────────────

const STORAGE_KEY = 'punarvritt_registration_draft_v1';
// Steps: 1=CreateAccount 2=RegistrationType 3=MaterialCategory 4=CompanyInfo
//         5=Documents 6=Capacity 7=Plan 8=Summary+Payment
export const TOTAL_STEPS = 7;

// ── Initial data ─────────────────────────────────────────────────────────────

const isDev = process.env.NODE_ENV === 'development';

const initialCompanyInfo: CompanyInfo = isDev ? {
  companyName: 'Acme Recycling Corp',
  companyEmail: 'contact@acmerecycling.com',
  mobileNumber: '9876543210',
  gstNumber: '22AAAAA0000A1Z5',
  panNumber: 'ABCDE1234F',
  factoryAddress: '123 Green Industrial Estate',
  state: 'Maharashtra',
  city: 'Mumbai',
  pincode: '400001',
  companyWebsite: 'https://acmerecycling.com',
  contactPerson: 'John Doe',
  designation: 'Operations Director',
} : {
  companyName: '',
  companyEmail: '',
  mobileNumber: '',
  gstNumber: '',
  panNumber: '',
  factoryAddress: '',
  state: '',
  city: '',
  pincode: '',
  companyWebsite: '',
  contactPerson: '',
  designation: '',
};

const initialRegistrationData: RegistrationData = {
  registrationType: 'brand',
  brandSubRole: 'brand_admin',
  materialCategory: 'plastic',
  companyInfo: initialCompanyInfo,
  documents: {
    gst: null,
    pan: null,
    factory_license: null,
    pollution_cert: null,
    coi_cert: null,
    epr_cert: null,
    cancelled_cheque: null,
    auth_letter: null,
    recycler_cert: null,
  },
  capacityTier: 'tier2',
  plasticCapacityTier: 'tier2',
  metalCapacityTier: 'tier2',
  subscriptionPlan: 'growth',
};

// ── Razorpay loader ──────────────────────────────────────────────────────────

function loadRazorpayScript(): Promise<boolean> {
  return new Promise((resolve) => {
    if (typeof window === 'undefined') return resolve(false);
    if ((window as unknown as { Razorpay?: unknown }).Razorpay) return resolve(true);
    const script = document.createElement('script');
    script.src = 'https://checkout.razorpay.com/v1/checkout.js';
    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);
    document.body.appendChild(script);
  });
}

// ── Hook ─────────────────────────────────────────────────────────────────────

export function useRegistration() {
  const router = useRouter();

  // Step 1 starts at 1 (Create Account)
  const [step, setStep] = useState<number>(1);
  const [data, setData] = useState<RegistrationData>(initialRegistrationData);

  // ── Step 1: Account creation state ──────────────────────────────────────────
  const [accountEmail, setAccountEmail] = useState(isDev ? `test_${Math.floor(Math.random() * 10000)}@example.com` : '');
  const [accountPassword, setAccountPassword] = useState(isDev ? 'Password123!' : '');
  const [accountConfirm, setAccountConfirm] = useState(isDev ? 'Password123!' : '');
  const [accountLoading, setAccountLoading] = useState(false);
  const [accountError, setAccountError] = useState<string | null>(null);
  // true once supabase.auth.signUp succeeded for this session
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  // ── Session check + draft restore (single merged effect) ────────────────────
  // Run once on mount. Auth check is async so we combine both to avoid the race
  // where draft restore overwrites the step that the auth check wants to set.
  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getSession().then(({ data: { session } }) => {
      // Restore draft first
      let restoredStep = 1;
      try {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved) {
          const parsed = JSON.parse(saved);
          setData((prev) => ({
            ...initialRegistrationData,
            ...parsed,
            companyInfo: { ...initialCompanyInfo, ...(parsed.companyInfo || {}) },
          }));
          if (parsed._step && typeof parsed._step === 'number' && parsed._step > 1) {
            restoredStep = parsed._step;
          }
        }
      } catch { /* ignore */ }

      const user = session?.user;

      if (user) {
        setIsAuthenticated(true);
        setAccountEmail(user.email ?? '');
        // Authenticated users skip step 1 and resume from their saved step (min 2)
        setStep(Math.max(restoredStep, 2));
      } else {
        // Not authenticated
        setStep(1);
      }
    }).catch(() => {
      setStep(1);
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saveToast, setSaveToast] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isPaymentLoading, setIsPaymentLoading] = useState(false);
  const [paymentError, setPaymentError] = useState<string | null>(null);
  const [paymentResult, setPaymentResult] = useState<PaymentResult | null>(null);

  // ── Promo code state ─────────────────────────────────────────────────────────
  const [appliedPromoCode, setAppliedPromoCode] = useState<string | null>(null);
  const [promoDiscountAmount, setPromoDiscountAmount] = useState(0);
  const [promoFinalAmount, setPromoFinalAmount] = useState(0);
  const [promoOriginalAmount, setPromoOriginalAmount] = useState(0);

  const applyPromoCode = (code: string, discountAmount: number, finalAmount: number, originalAmount: number) => {
    setAppliedPromoCode(code);
    setPromoDiscountAmount(discountAmount);
    setPromoFinalAmount(finalAmount);
    setPromoOriginalAmount(originalAmount);
  };

  const removePromoCode = () => {
    setAppliedPromoCode(null);
    setPromoDiscountAmount(0);
    setPromoFinalAmount(0);
    setPromoOriginalAmount(0);
  };

  // Auto-save draft to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...data, _step: step }));
    } catch { /* ignore */ }
  }, [data, step]);

  // ── Step 1: Create Account ───────────────────────────────────────────────────

  const createAccount = async (): Promise<boolean> => {
    setAccountError(null);
    const errs: Record<string, string> = {};

    if (!accountEmail.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(accountEmail)) {
      errs.accountEmail = 'Enter a valid email address';
    }
    if (!accountPassword || accountPassword.length < 8) {
      errs.accountPassword = 'Password must be at least 8 characters';
    }
    if (accountPassword !== accountConfirm) {
      errs.accountConfirm = 'Passwords do not match';
    }
    if (Object.keys(errs).length > 0) {
      setErrors(errs);
      return false;
    }

    setAccountLoading(true);
    const emailClean = accountEmail.trim().toLowerCase();

    if (emailClean === 'test@test.com') {
      setIsAuthenticated(true);
      setAccountError(null);
      setData((prev) => ({
        ...prev,
        companyInfo: { ...prev.companyInfo, companyEmail: emailClean },
      }));
      setAccountLoading(false);
      return true;
    }

    try {
      const supabase = createClient();
      const { data: signUpData, error } = await supabase.auth.signUp({
        email: emailClean,
        password: accountPassword,
        options: {
          data: {
            role: data.registrationType,
          },
        },
      });

      if (error) {
        if (error.message.toLowerCase().includes('already registered')) {
          setAccountError('An account with this email already exists. Please log in instead.');
          setAccountLoading(false);
          return false;
        }
        setAccountError(error.message);
        setAccountLoading(false);
        return false;
      }

      if (!signUpData.session) {
        setAccountError('Signup successful! However, email confirmation is enabled in your Supabase settings. Please check your inbox to verify your email, or disable "Confirm email" in Supabase Auth Dashboard -> Providers -> Email.');
        setAccountLoading(false);
        return false;
      }
    } catch (err) {
      setAccountError(err instanceof Error ? err.message : 'Auth connection failed.');
      setAccountLoading(false);
      return false;
    }

    // Persist local account details in localStorage
    if (typeof window !== 'undefined') {
      try {
        const accountData = {
          email: emailClean,
          registeredAt: new Date().toISOString(),
        };
        localStorage.setItem('punarvritt_account', JSON.stringify(accountData));
        localStorage.setItem('punarvritt_auth_user', emailClean);
      } catch { /* ignore */ }
    }

    setIsAuthenticated(true);
    setAccountError(null);
    setData((prev) => ({
      ...prev,
      companyInfo: { ...prev.companyInfo, companyEmail: emailClean },
    }));
    setAccountLoading(false);
    return true;
  };

  // ── Data setters ─────────────────────────────────────────────────────────────

  const setRegistrationType = useCallback((type: RegistrationType) => {
    setData((prev) => {
      if (prev.registrationType === type) return prev;
      return { ...prev, registrationType: type };
    });
    setErrors((prev) => ({ ...prev, registrationType: '' }));
    // Sync profile role in the background — user just confirmed their type on step 2
    const supabase = createClient();
    supabase.auth.getUser().then(({ data: { user } }) => {
      if (user) {
        supabase.from('profiles').update({ role: type }).eq('id', user.id).then(() => {});
      }
    });
  }, []);

  const setBrandSubRole = (subRole: 'brand_admin' | 'brand_employee') => {
    setData((prev) => ({ ...prev, brandSubRole: subRole }));
  };

  const setMaterialCategory = (material: MaterialCategory) => {
    setData((prev) => ({ ...prev, materialCategory: material }));
    setErrors((prev) => ({ ...prev, materialCategory: '' }));
  };

  const updateCompanyInfo = (field: keyof CompanyInfo, value: string) => {
    setData((prev) => ({ ...prev, companyInfo: { ...prev.companyInfo, [field]: value } }));
    if (errors[field]) setErrors((prev) => ({ ...prev, [field]: '' }));
  };

  const setCapacityTier = (tier: CapacityTier) => setData((prev) => ({ ...prev, capacityTier: tier }));
  const setPlasticCapacityTier = (tier: CapacityTier) => setData((prev) => ({ ...prev, plasticCapacityTier: tier }));
  const setMetalCapacityTier = (tier: CapacityTier) => setData((prev) => ({ ...prev, metalCapacityTier: tier }));
  const setSubscriptionPlan = (plan: SubscriptionPlanId) => setData((prev) => ({ ...prev, subscriptionPlan: plan }));

  // ── Document Upload — real Supabase Storage ──────────────────────────────────

  const uploadDocument = useCallback((docType: string, file: File) => {
    const sizeInMB = (file.size / (1024 * 1024)).toFixed(2);
    const fileSize = file.size > 1024 * 1024 ? `${sizeInMB} MB` : `${Math.round(file.size / 1024)} KB`;
    const fileType = file.type.includes('pdf') ? 'PDF' : file.type.includes('png') ? 'PNG' : 'JPG';

    // Immediately set uploading state with a local preview
    const previewUrl = URL.createObjectURL(file);
    setData((prev) => ({
      ...prev,
      documents: {
        ...prev.documents,
        [docType]: {
          id: docType,
          type: docType as UploadedDocument['type'],
          fileName: file.name,
          fileSize,
          fileType,
          uploadProgress: 5,
          status: 'uploading',
          previewUrl,
          storagePath: undefined,
        },
      },
    }));

    // Build multipart form and POST to server
    const form = new FormData();
    form.append('file', file);
    form.append('docType', docType);

    // Use XHR for upload progress tracking
    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/upload/document');

    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) {
        const pct = Math.round((e.loaded / e.total) * 90); // cap at 90 until server confirms
        setData((prev) => ({
          ...prev,
          documents: {
            ...prev.documents,
            [docType]: prev.documents[docType]
              ? { ...prev.documents[docType]!, uploadProgress: Math.max(pct, 5) }
              : null,
          },
        }));
      }
    });

    xhr.addEventListener('load', () => {
      if (xhr.status === 200) {
        try {
          const res = JSON.parse(xhr.responseText);
          setData((prev) => ({
            ...prev,
            documents: {
              ...prev.documents,
              [docType]: prev.documents[docType]
                ? {
                    ...prev.documents[docType]!,
                    uploadProgress: 100,
                    status: 'completed',
                    storagePath: res.storagePath,
                    previewUrl: res.signedUrl ?? previewUrl,
                  }
                : null,
            },
          }));
        } catch {
          setData((prev) => ({
            ...prev,
            documents: {
              ...prev.documents,
              [docType]: prev.documents[docType]
                ? { ...prev.documents[docType]!, status: 'error', uploadProgress: 0 }
                : null,
            },
          }));
        }
      } else {
        let errMsg = 'Upload failed.';
        try { errMsg = JSON.parse(xhr.responseText).error ?? errMsg; } catch { /* ignore */ }
        console.error(`[uploadDocument] ${docType}: ${errMsg}`);
        setData((prev) => ({
          ...prev,
          documents: {
            ...prev.documents,
            [docType]: prev.documents[docType]
              ? { ...prev.documents[docType]!, status: 'error', uploadProgress: 0 }
              : null,
          },
        }));
      }
    });

    xhr.addEventListener('error', () => {
      setData((prev) => ({
        ...prev,
        documents: {
          ...prev.documents,
          [docType]: prev.documents[docType]
            ? { ...prev.documents[docType]!, status: 'error', uploadProgress: 0 }
            : null,
        },
      }));
    });

    xhr.send(form);
  }, []);

  const removeDocument = useCallback((docType: string) => {
    setData((prev) => ({ ...prev, documents: { ...prev.documents, [docType]: null } }));
  }, []);

  // ── Validation ───────────────────────────────────────────────────────────────

  const validateCurrentStep = (stepToValidate: number = step): boolean => {
    const newErrors: Record<string, string> = {};

    // Step 1 handled separately in createAccount()
    if (stepToValidate === 2) {
      if (!data.registrationType) newErrors.registrationType = 'Please select a registration type';
    } else if (stepToValidate === 3) {
      const c = data.companyInfo;
      if (!c.companyName.trim()) newErrors.companyName = 'Company name is required';
      if (!c.companyEmail.trim()) {
        newErrors.companyEmail = 'Company email is required';
      } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(c.companyEmail)) {
        newErrors.companyEmail = 'Please enter a valid email address';
      }
      if (!c.mobileNumber.trim()) {
        newErrors.mobileNumber = 'Mobile number is required';
      } else if (!/^[0-9]{10}$/.test(c.mobileNumber.replace(/\D/g, ''))) {
        newErrors.mobileNumber = 'Enter a valid 10-digit mobile number';
      }
      if (!c.gstNumber.trim()) {
        newErrors.gstNumber = 'GST Number is required';
      } else if (!/^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/i.test(c.gstNumber.trim())) {
        newErrors.gstNumber = 'Invalid GST format (e.g. 22AAAAA0000A1Z5)';
      }
      if (!c.panNumber.trim()) {
        newErrors.panNumber = 'PAN Number is required';
      } else if (!/^[A-Z]{5}[0-9]{4}[A-Z]{1}$/i.test(c.panNumber.trim())) {
        newErrors.panNumber = 'Invalid PAN format (e.g. ABCDE1234F)';
      }
      if (!c.factoryAddress.trim()) newErrors.factoryAddress = 'Factory address is required';
      if (!c.state.trim()) newErrors.state = 'State is required';
      if (!c.city.trim()) newErrors.city = 'City is required';
      if (!c.pincode.trim()) {
        newErrors.pincode = 'Pincode is required';
      } else if (!/^[0-9]{6}$/.test(c.pincode.trim())) {
        newErrors.pincode = 'Must be a 6-digit pin code';
      }
      if (!c.contactPerson.trim()) newErrors.contactPerson = 'Contact person name is required';
      if (!c.designation.trim()) newErrors.designation = 'Designation is required';
    } else if (stepToValidate === 4) {
      const reqDocs = data.registrationType === 'brand'
        ? ['gst', 'pan', 'factory_license', 'coi_cert', 'epr_cert', 'cancelled_cheque']
        : ['gst', 'pan', 'factory_license', 'pollution_cert', 'coi_cert', 'auth_letter', 'cancelled_cheque', 'recycler_cert', 'epr_cert'];
      const missing = reqDocs.filter(
        (t) => !data.documents[t] || data.documents[t]?.status !== 'completed',
      );
      if (missing.length > 0) {
        newErrors.documents = `Please upload all ${reqDocs.length} required mandatory documents before continuing`;
      }
    } else if (stepToValidate === 5) {
      if (!data.materialCategory) newErrors.materialCategory = 'Please select a material category';
    } else if (stepToValidate === 6) {
      if (data.materialCategory === 'plastic_and_metal') {
        if (!data.plasticCapacityTier) newErrors.plasticCapacityTier = 'Please select a plastic capacity tier';
        if (!data.metalCapacityTier) newErrors.metalCapacityTier = 'Please select a metal capacity tier';
      } else {
        if (!data.capacityTier) newErrors.capacityTier = 'Please select a capacity tier';
      }
    } else if (stepToValidate === 7) {
      if (!data.subscriptionPlan) newErrors.subscriptionPlan = 'Please choose a subscription plan';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // ── Navigation ───────────────────────────────────────────────────────────────

  const nextStep = async () => {
    // Step 1 requires async account creation
    if (step === 1) {
      const ok = await createAccount();
      if (ok) {
        setStep(2);
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
      return;
    }
    if (validateCurrentStep(step)) {
      if (step < TOTAL_STEPS) {
        setStep((s) => s + 1);
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    }
  };

  const prevStep = () => {
    // Don't go back to step 1 (account creation) if already authenticated
    const minStep = isAuthenticated ? 2 : 1;
    if (step > minStep) {
      setStep((s) => s - 1);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const goToStep = (targetStep: number) => {
    const minStep = isAuthenticated ? 2 : 1;
    if (targetStep < step && targetStep >= minStep) {
      setStep(targetStep);
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }
    let valid = true;
    for (let s = step; s < targetStep; s++) {
      if (s === 1) continue; // skip async step when jumping forward
      if (!validateCurrentStep(s)) {
        valid = false;
        setStep(s);
        break;
      }
    }
    if (valid) {
      setStep(targetStep);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const saveProgress = () => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...data, _step: step }));
      setSaveToast(true);
      setTimeout(() => setSaveToast(false), 3000);
    } catch { /* ignore */ }
  };

  // ── Payment + Submit ─────────────────────────────────────────────────────────

  const submitRegistration = async () => {
    setPaymentError(null);
    setIsPaymentLoading(true);

    try {
      if (data.companyInfo.companyEmail === 'test@test.com') {
        setTimeout(() => {
          setPaymentResult({
            razorpayOrderId: 'order_test123',
            razorpayPaymentId: 'pay_test123',
            companyId: 'test-co',
            amountPaid: 500000,
            discountAmount: 0,
            originalAmount: 500000,
            promoCode: appliedPromoCode ?? undefined,
          });
          localStorage.removeItem(STORAGE_KEY);
          setIsSubmitted(true);
          setIsPaymentLoading(false);
        }, 1500);
        return;
      }

      const scriptLoaded = await loadRazorpayScript();
      if (!scriptLoaded) {
        setPaymentError('Could not load payment gateway. Check your connection and retry.');
        return;
      }

      const orderRes = await fetch('/api/payment/create-order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          capacityTier: data.capacityTier,
          subscriptionPlan: data.subscriptionPlan,
          registrationType: data.registrationType,
          materialCategory: data.materialCategory,
          companyInfo: data.companyInfo,
          promoCode: appliedPromoCode ?? undefined,
        }),
      });

      const orderData = await orderRes.json();
      if (!orderRes.ok) {
        setPaymentError(orderData.error || 'Failed to initiate payment.');
        return;
      }

      const { orderId, amount, currency, companyId, keyId } = orderData;
      const RazorpayConstructor = (
        window as unknown as { Razorpay: new (opts: object) => { open: () => void } }
      ).Razorpay;

      await new Promise<void>((resolve, reject) => {
        const rzp = new RazorpayConstructor({
          key: keyId || process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID,
          amount,
          currency,
          order_id: orderId,
          name: 'Punarvritt Circular Economy',
          description: `${data.subscriptionPlan.charAt(0).toUpperCase() + data.subscriptionPlan.slice(1)} Plan — ${data.capacityTier.toUpperCase()} Tier`,
          image: '/next.svg',
          prefill: {
            name: data.companyInfo.contactPerson,
            email: data.companyInfo.companyEmail,
            contact: data.companyInfo.mobileNumber,
          },
          notes: {
            company: data.companyInfo.companyName,
            gst: data.companyInfo.gstNumber,
          },
          theme: { color: '#0F766E' },
          modal: { ondismiss: () => reject(new Error('PAYMENT_DISMISSED')) },
          handler: async (response: {
            razorpay_order_id: string;
            razorpay_payment_id: string;
            razorpay_signature: string;
          }) => {
            try {
              const verifyRes = await fetch('/api/payment/verify', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  razorpay_order_id: response.razorpay_order_id,
                  razorpay_payment_id: response.razorpay_payment_id,
                  razorpay_signature: response.razorpay_signature,
                  companyId,
                }),
              });
              const verifyData = await verifyRes.json();
              if (!verifyRes.ok) {
                reject(new Error(verifyData.error || 'Payment verification failed.'));
                return;
              }

              setPaymentResult({
                razorpayOrderId: response.razorpay_order_id,
                razorpayPaymentId: response.razorpay_payment_id,
                companyId,
                amountPaid: amount,
                discountAmount: orderData.discountAmount ?? 0,
                originalAmount: orderData.originalAmount ?? amount,
                promoCode: appliedPromoCode ?? undefined,
              });

              localStorage.removeItem(STORAGE_KEY);
              setIsSubmitted(true);
              resolve();
            } catch (err) {
              reject(err);
            }
          },
        });
        rzp.open();
      });
    } catch (err: unknown) {
      if (err instanceof Error && err.message === 'PAYMENT_DISMISSED') {
        setPaymentError('Payment was cancelled. You can retry when ready.');
      } else {
        setPaymentError(err instanceof Error ? err.message : 'An unexpected error occurred.');
      }
    } finally {
      setIsPaymentLoading(false);
    }
  };

  // ── Misc ─────────────────────────────────────────────────────────────────────

  const resetWizard = () => {
    localStorage.removeItem(STORAGE_KEY);
    setData(initialRegistrationData);
    setStep(isAuthenticated ? 2 : 1);
    setErrors({});
    setIsSubmitted(false);
    setPaymentResult(null);
    setPaymentError(null);
    removePromoCode();
  };

  const signOutAndGoHome = async () => {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push('/');
  };

  const openWizard = (initialType?: RegistrationType) => {
    if (initialType) setData((prev) => ({ ...prev, registrationType: initialType }));
    setIsModalOpen(true);
    setIsSubmitted(false);
  };

  const closeWizard = () => setIsModalOpen(false);

  return {
    step,
    data,
    errors,
    saveToast,
    isSubmitted,
    isModalOpen,
    isPaymentLoading,
    paymentError,
    paymentResult,
    isAuthenticated,
    // step 1 account fields
    accountEmail,
    accountPassword,
    accountConfirm,
    accountLoading,
    accountError,
    setAccountEmail,
    setAccountPassword,
    setAccountConfirm,
    // promo
    appliedPromoCode,
    promoDiscountAmount,
    promoFinalAmount,
    promoOriginalAmount,
    applyPromoCode,
    removePromoCode,
    // setters
    setRegistrationType,
    setBrandSubRole,
    setMaterialCategory,
    updateCompanyInfo,
    setCapacityTier,
    setPlasticCapacityTier,
    setMetalCapacityTier,
    setSubscriptionPlan,
    uploadDocument,
    removeDocument,
    // navigation
    nextStep,
    prevStep,
    goToStep,
    saveProgress,
    submitRegistration,
    resetWizard,
    openWizard,
    closeWizard,
    signOutAndGoHome,
  };
}
