export type BrandSubRole = 'brand_admin' | 'brand_employee';

export type RegistrationType = 'brand' | 'recycler';

export type MaterialCategory = 'plastic' | 'metal' | 'plastic_and_metal';

export type CapacityTier = 'tier1' | 'tier2' | 'tier3' | 'tier4';

export type SubscriptionPlanId = 'starter' | 'growth' | 'enterprise';

export interface CompanyInfo {
  companyName: string;
  companyEmail: string;
  mobileNumber: string;
  gstNumber: string;
  panNumber: string;
  factoryAddress: string;
  state: string;
  city: string;
  pincode: string;
  companyWebsite: string;
  contactPerson: string;
  designation: string;
}

export interface UploadedDocument {
  id: string;
  type: 'gst' | 'pan' | 'factory_license' | 'pollution_cert' | 'coi_cert' | 'epr_cert' | 'cancelled_cheque' | 'auth_letter' | 'recycler_cert';
  fileName: string;
  fileSize: string;
  fileType: string;
  uploadProgress: number;
  status: 'uploading' | 'completed' | 'error';
  previewUrl?: string;
  storagePath?: string; // path in Supabase Storage after successful upload
}

export interface RegistrationData {
  registrationType: RegistrationType;
  brandSubRole?: BrandSubRole;
  materialCategory: MaterialCategory;
  companyInfo: CompanyInfo;
  documents: Record<string, UploadedDocument | null>;
  capacityTier: CapacityTier;
  plasticCapacityTier?: CapacityTier;
  metalCapacityTier?: CapacityTier;
  subscriptionPlan: SubscriptionPlanId;
}

export interface CapacityTierDetail {
  id: CapacityTier;
  title: string;
  range: string;
  description: string;
  recommendedFor: string;
}

export interface PlanDetail {
  id: SubscriptionPlanId;
  name: string;
  tagline: string;
  popular?: boolean;
  features: string[];
}

export interface PricingForTier {
  tier: CapacityTier;
  starter: { price: string; period: string };
  growth: { price: string; period: string };
  enterprise: { price: string; period: string };
}

/** Returned after a successful Razorpay payment + server-side verification. */
export interface PaymentResult {
  razorpayOrderId: string;
  razorpayPaymentId: string;
  companyId: string;
  amountPaid: number;       // final amount in paise (after discount)
  originalAmount: number;   // pre-discount amount in paise
  discountAmount: number;   // discount applied in paise
  promoCode?: string;       // promo code used, if any
}
