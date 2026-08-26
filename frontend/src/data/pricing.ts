import { CapacityTierDetail, PlanDetail, PricingForTier, CapacityTier, SubscriptionPlanId, RegistrationType } from '../types/registration';

export const BRAND_CAPACITY_TIERS: CapacityTierDetail[] = [
  {
    id: 'tier1',
    title: 'Tier 1',
    range: '< 100 MT/year',
    description: 'Ideal for emerging brand owners, regional distributors, and small PIBO aggregators.',
    recommendedFor: 'Emerging Brands & Regional PIBOs',
  },
  {
    id: 'tier2',
    title: 'Tier 2',
    range: '100–500 MT/year',
    description: 'Designed for growing FMCG and packaging brands with multi-region compliance needs.',
    recommendedFor: 'Mid-Sized Brands & Distributors',
  },
  {
    id: 'tier3',
    title: 'Tier 3',
    range: '500–2,000 MT/year',
    description: 'High-volume national brands managing large annual packaging EPR targets.',
    recommendedFor: 'Large National Brands & Producers',
  },
  {
    id: 'tier4',
    title: 'Tier 4',
    range: '> 2,000 MT/year',
    description: 'Enterprise conglomerate brand owners requiring custom enterprise compliance automation.',
    recommendedFor: 'Multinational Enterprise PIBOs',
  },
];

export const RECYCLER_CAPACITY_TIERS: CapacityTierDetail[] = [
  {
    id: 'tier1',
    title: 'Tier 1',
    range: '< 100 MT/year',
    description: 'Ideal for local waste aggregators and small certified recycling units.',
    recommendedFor: 'Local Aggregators & Small Recyclers',
  },
  {
    id: 'tier2',
    title: 'Tier 2',
    range: '100–500 MT/year',
    description: 'Designed for regional plastic/metal recycling facilities with steady monthly processing.',
    recommendedFor: 'Regional Processing Facilities',
  },
  {
    id: 'tier3',
    title: 'Tier 3',
    range: '500–2,000 MT/year',
    description: 'High-capacity industrial recyclers issuing large volumes of EPR credit certificates.',
    recommendedFor: 'Industrial Recycling Hubs',
  },
  {
    id: 'tier4',
    title: 'Tier 4',
    range: '> 2,000 MT/year',
    description: 'Large multi-facility recycling enterprises requiring customized API integration.',
    recommendedFor: 'Enterprise Recycling Networks',
  },
];

export const CAPACITY_TIERS: CapacityTierDetail[] = BRAND_CAPACITY_TIERS;

export function getCapacityTiers(registrationType?: RegistrationType) {
  return registrationType === 'recycler' ? RECYCLER_CAPACITY_TIERS : BRAND_CAPACITY_TIERS;
}

export const PRICING_MATRIX: Record<CapacityTier, PricingForTier> = {
  tier1: {
    tier: 'tier1',
    starter: { price: '₹45,000', period: 'year' },
    growth: { price: '₹95,000', period: 'year' },
    enterprise: { price: '₹1,60,000', period: 'year' },
  },
  tier2: {
    tier: 'tier2',
    starter: { price: '₹85,000', period: 'year' },
    growth: { price: '₹1,80,000', period: 'year' },
    enterprise: { price: '₹3,20,000', period: 'year' },
  },
  tier3: {
    tier: 'tier3',
    starter: { price: '₹1,50,000', period: 'year' },
    growth: { price: '₹3,10,000', period: 'year' },
    enterprise: { price: '₹5,50,000', period: 'year' },
  },
  tier4: {
    tier: 'tier4',
    starter: { price: 'Custom', period: 'Contact Sales' },
    growth: { price: 'Custom', period: 'Contact Sales' },
    enterprise: { price: 'Custom Pricing', period: 'Contact Sales' },
  },
};

export const STARTER_FEATURES: string[] = [
  'Dashboard & Company Profile',
  'Document Vault',
  'Basic EPR Tracking',
  'Manual Invoice Management',
  'Marketplace Access',
  'Compliance Reports',
  'BRSR Report Generation',
  'Audit Readiness Score',
];

export const GROWTH_FEATURES: string[] = [
  'Everything in Starter',
  'Advanced Analytics',
  'WhatsApp Notifications',
  'Priority Support',
  'Bi-weekly Account Call',
  'Deadline Reminders',
];

export const ENTERPRISE_FEATURES: string[] = [
  'Everything in Growth',
  'AI Compliance Insights',
  'Dedicated Account Manager',
  'Automatic Invoice Sync',
  'Custom Reports',
  '24×7 Auditor Assistance',
  'Priority Support',
];

export const PLAN_DETAILS: PlanDetail[] = [
  {
    id: 'starter',
    name: 'Starter',
    tagline: 'Essential EPR compliance and marketplace listing for operational needs.',
    popular: false,
    features: STARTER_FEATURES,
  },
  {
    id: 'growth',
    name: 'Growth',
    tagline: 'Complete automation with priority support and real-time alerts.',
    popular: true,
    features: GROWTH_FEATURES,
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    tagline: 'Customized scale, dedicated auditor assistance, and AI insights.',
    popular: false,
    features: ENTERPRISE_FEATURES,
  },
];

export const BRAND_REQUIRED_DOCUMENTS = [
  {
    id: 'gst',
    title: 'GST Certificate',
    description: 'Upload valid GSTIN Registration Certificate (Form GST REG-06)',
    required: true,
    allowedTypes: 'PDF, PNG, JPG',
  },
  {
    id: 'pan',
    title: 'PAN Card',
    description: 'Company or Authorized Signatory Permanent Account Number card',
    required: true,
    allowedTypes: 'PDF, PNG, JPG',
  },
  {
    id: 'factory_license',
    title: 'Factory License',
    description: 'Valid state industrial factory permit or shop registration',
    required: true,
    allowedTypes: 'PDF, PNG, JPG',
  },
  {
    id: 'coi_cert',
    title: 'Certificate of Incorporation',
    description: 'Upload ROC Company Incorporation Certificate or Partnership Deed',
    required: true,
    allowedTypes: 'PDF, PNG, JPG',
  },
  {
    id: 'epr_cert',
    title: 'EPR Certificate',
    description: 'CPCB Registration or existing EPR fulfillments record',
    required: true,
    allowedTypes: 'PDF, PNG, JPG',
  },
  {
    id: 'cancelled_cheque',
    title: 'Cancelled Cheque',
    description: 'Upload company cancelled cheque or bank statement for account verification',
    required: true,
    allowedTypes: 'PDF, PNG, JPG',
  },
];

export const RECYCLER_REQUIRED_DOCUMENTS = [
  {
    id: 'gst',
    title: 'GST Certificate',
    description: 'Upload valid GSTIN Registration Certificate (Form GST REG-06)',
    required: true,
    allowedTypes: 'PDF, PNG, JPG',
  },
  {
    id: 'pan',
    title: 'PAN Card',
    description: 'Company or Authorized Signatory Permanent Account Number card',
    required: true,
    allowedTypes: 'PDF, PNG, JPG',
  },
  {
    id: 'factory_license',
    title: 'Factory License',
    description: 'Valid state industrial factory permit or shop registration',
    required: true,
    allowedTypes: 'PDF, PNG, JPG',
  },
  {
    id: 'pollution_cert',
    title: 'Pollution Certificate',
    description: 'Consent to Operate (CTO) or Consent to Establish (CTE) from SPCB/PCC',
    required: true,
    allowedTypes: 'PDF, PNG, JPG',
  },
  {
    id: 'coi_cert',
    title: 'Certificate of Incorporation',
    description: 'Upload ROC Company Incorporation Certificate or Partnership Deed',
    required: true,
    allowedTypes: 'PDF, PNG, JPG',
  },
  {
    id: 'auth_letter',
    title: 'Authorized Signatory Letter',
    description: 'Upload Board Resolution or Authorization Letter for authorized signatory',
    required: true,
    allowedTypes: 'PDF, PNG, JPG',
  },
  {
    id: 'cancelled_cheque',
    title: 'Cancelled Cheque',
    description: 'Upload company cancelled cheque or bank statement for account verification',
    required: true,
    allowedTypes: 'PDF, PNG, JPG',
  },
  {
    id: 'recycler_cert',
    title: 'Recycler Authorized Certification',
    description: 'Upload CPCB/SPCB Authorized Recycler Registration Certificate or Processing License',
    required: true,
    allowedTypes: 'PDF, PNG, JPG',
  },
  {
    id: 'epr_cert',
    title: 'EPR Certificate',
    description: 'CPCB Registration or existing EPR fulfillments record',
    required: true,
    allowedTypes: 'PDF, PNG, JPG',
  },
];

export const REQUIRED_DOCUMENTS = BRAND_REQUIRED_DOCUMENTS;

/**
 * Numeric amounts in paise (INR × 100) for each tier/plan combination.
 * Used server-side when creating Razorpay orders.
 * tier4 is 0 — requires a custom sales quote and cannot be paid online.
 */
export const PRICE_AMOUNTS: Record<string, Record<string, number>> = {
  tier1: { starter: 4500000, growth: 9500000, enterprise: 16000000 },
  tier2: { starter: 8500000, growth: 18000000, enterprise: 32000000 },
  tier3: { starter: 15000000, growth: 31000000, enterprise: 55000000 },
  tier4: { starter: 0, growth: 0, enterprise: 0 },
};

export function getRequiredDocuments(registrationType?: RegistrationType) {
  return registrationType === 'brand' ? BRAND_REQUIRED_DOCUMENTS : RECYCLER_REQUIRED_DOCUMENTS;
}

export const INDIAN_STATES = [
  'Andhra Pradesh',
  'Arunachal Pradesh',
  'Assam',
  'Bihar',
  'Chhattisgarh',
  'Goa',
  'Gujarat',
  'Haryana',
  'Himachal Pradesh',
  'Jharkhand',
  'Karnataka',
  'Kerala',
  'Madhya Pradesh',
  'Maharashtra',
  'Manipur',
  'Meghalaya',
  'Mizoram',
  'Nagaland',
  'Odisha',
  'Punjab',
  'Rajasthan',
  'Sikkim',
  'Tamil Nadu',
  'Telangana',
  'Tripura',
  'Uttar Pradesh',
  'Uttarakhand',
  'West Bengal',
  'Delhi NCR',
  'Dadra & Nagar Haveli and Daman & Diu',
  'Puducherry',
];
