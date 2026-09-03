import uuid
from datetime import datetime
from decimal import Decimal

from typing import Literal, Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models import (
    CompanyType,
    DiscountType,
    DocumentCategory,
    MaterialType,
    DocumentStatus,
    MemberRole,
    MemberStatus,
    PackType,
    PaymentStatus,
    PurchaseStatus,
    ArrivalStatus,
    InvoiceProofCategory,
    RefundRequestStatus,
    SystemRole,
    WalletRechargeStatus,
    PaymentMethod,
    WithdrawalStatus,
)



# ============================================================================
# profiles
# ============================================================================
class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    system_role: SystemRole
    created_at: datetime
    updated_at: datetime


# ============================================================================
# companies
# ============================================================================
class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    clerk_org_id: str
    owner_id: str
    name: str
    company_email: str
    mobile_number: str
    gst_number: str
    company_pan_number: str
    factory_address: str
    state: str
    city: str
    pincode: str
    company_website: str | None
    contact_person_name: str
    contact_person_email: str | None
    designation: str
    
    # Recycler Profile fields
    established_year: int | None = None
    cpcb_id: str | None = None
    monthly_plant_capacity_mt: int | None = None
    esg_rating: int | None = None
    dispatch_lead_time_days: str | None = None
    
    material: MaterialType
    company_type: CompanyType
    pack: PackType
    tier: int
    epr_credits_available:  Decimal
    epr_credits_required:   Decimal
    epr_credits_purchased:  Decimal
    epr_credits_utilized:   Decimal
    wallet_balance: Decimal
    frozen_wallet_balance: Decimal
    created_at: datetime
    updated_at: datetime


class BrandProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    city: str
    state: str
    contact_person_name: str
    mobile_number: str
    company_email: str
    gst_number: str


class RecyclerProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    city: str
    state: str
    established_year: int | None = None
    contact_person_name: str
    mobile_number: str
    company_email: str
    gst_number: str
    cpcb_id: str | None = None
    monthly_plant_capacity_mt: int | None = None
    esg_rating: int | None = None
    dispatch_lead_time_days: str | None = None


class CompanyEmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    clerk_org_id: str
    name: str
    company_type: CompanyType
    created_at: datetime
    updated_at: datetime


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255, strip_whitespace=True)
    company_email: EmailStr | None = Field(default=None)
    mobile_number: str | None = Field(default=None, min_length=1, max_length=31, strip_whitespace=True)
    gst_number: str | None = Field(default=None, min_length=1, max_length=127, strip_whitespace=True)
    company_pan_number: str | None = Field(default=None, min_length=10, max_length=10, strip_whitespace=True)
    factory_address: str | None = Field(default=None, min_length=1, max_length=1024, strip_whitespace=True)
    state: str | None = Field(default=None, min_length=1, max_length=127, strip_whitespace=True)
    city: str | None = Field(default=None, min_length=1, max_length=127, strip_whitespace=True)
    pincode: str | None = Field(default=None, min_length=1, max_length=31, strip_whitespace=True)
    company_website: str | None = Field(default=None, max_length=2048, strip_whitespace=True)
    contact_person_name: str | None = Field(default=None, min_length=1, max_length=255, strip_whitespace=True)
    contact_person_email: EmailStr | None = Field(default=None)
    designation: str | None = Field(default=None, min_length=1, max_length=255, strip_whitespace=True)
    
    established_year: int | None = Field(default=None, ge=1800, le=2100)
    cpcb_id: str | None = Field(default=None, max_length=255, strip_whitespace=True)
    monthly_plant_capacity_mt: int | None = Field(default=None, ge=0)
    esg_rating: int | None = Field(default=None, ge=0, le=100)
    dispatch_lead_time_days: str | None = Field(default=None, max_length=255, strip_whitespace=True)
    
    material: MaterialType | None = Field(default=None)

    @model_validator(mode="after")
    def validate_name_not_null(self) -> "CompanyUpdate":
        # self.model_fields_set contains fields explicitly provided in the request
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name cannot be null")
        return self


class CompanyPlanUpdate(BaseModel):
    company_type: CompanyType
    pack: PackType
    tier: int = Field(ge=1, le=4)


# ============================================================================
# company_members
# ============================================================================
class CompanyMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    profile_id: str
    member_role: MemberRole
    status: MemberStatus
    created_at: datetime
    updated_at: datetime


class CompanyMemberStatusUpdate(BaseModel):
    status: MemberStatus

class CompanyMemberRoleUpdate(BaseModel):
    member_role: MemberRole


# ============================================================================
# documents
# ============================================================================
class DocumentPresignRequest(BaseModel):
    file_name: str = Field(min_length=1, max_length=255, pattern=r"^[^/\\\x00]+$")
    file_type: str = Field(min_length=1, max_length=127)  # MIME type
    file_size_bytes: int = Field(gt=0)
    category: DocumentCategory = DocumentCategory.OTHER

    @model_validator(mode="after")
    def validate_file(self) -> "DocumentPresignRequest":
        ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".docx", ".xlsx"}
        ALLOWED_MIME_TYPES = {
            "application/pdf",
            "image/jpeg",
            "image/png",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }
        EXT_TO_MIME: dict[str, str] = {
            ".pdf":  "application/pdf",
            ".jpg":  "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png":  "image/png",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }
        ext = ""
        if "." in self.file_name:
            ext = self.file_name[self.file_name.rindex("."):].lower()
        if ext not in ALLOWED_EXTENSIONS or self.file_type not in ALLOWED_MIME_TYPES:
            raise ValueError("File type not allowed. Allowed types are: PDF, JPG, PNG, DOCX, XLSX")
        if EXT_TO_MIME.get(ext) != self.file_type:
            raise ValueError(
                f"file_type '{self.file_type}' does not match the extension '{ext}'"
            )
        return self


class DocumentPresignResponse(BaseModel):
    upload_url: str
    storage_key: str
    expires_in_seconds: int


class DocumentCreate(BaseModel):
    storage_key: str = Field(min_length=1, max_length=1024)
    file_name: str = Field(min_length=1, max_length=255, pattern=r"^[^/\\\x00]+$")
    file_size_bytes: int = Field(gt=0)
    file_type: str = Field(min_length=1, max_length=127)
    category: DocumentCategory = DocumentCategory.OTHER

    @model_validator(mode="after")
    def validate_file(self) -> "DocumentCreate":
        ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".docx", ".xlsx"}
        ALLOWED_MIME_TYPES = {
            "application/pdf",
            "image/jpeg",
            "image/png",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }
        EXT_TO_MIME: dict[str, str] = {
            ".pdf":  "application/pdf",
            ".jpg":  "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png":  "image/png",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }
        ext = ""
        if "." in self.file_name:
            ext = self.file_name[self.file_name.rindex("."):].lower()
        if ext not in ALLOWED_EXTENSIONS or self.file_type not in ALLOWED_MIME_TYPES:
            raise ValueError("File type not allowed. Allowed types are: PDF, JPG, PNG, DOCX, XLSX")
        if EXT_TO_MIME.get(ext) != self.file_type:
            raise ValueError(
                f"file_type '{self.file_type}' does not match the extension '{ext}'"
            )
        return self


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    uploaded_by_profile_id: str
    file_name: str
    storage_key: str
    file_size_bytes: int
    file_type: str
    category: DocumentCategory
    status: DocumentStatus
    rejection_reason: str | None = None
    verified_by: str | None = None
    verified_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class DocumentVerifyRequest(BaseModel):
    status: Literal["VERIFIED", "REJECTED"]
    rejection_reason: str | None = Field(default=None, strip_whitespace=True, min_length=1)

    @model_validator(mode="after")
    def validate_rejection(self) -> "DocumentVerifyRequest":
        if self.status == "REJECTED":
            if not getattr(self, "rejection_reason", None):
                raise ValueError("rejection_reason is required when rejecting a document")
        else:
            if getattr(self, "rejection_reason", None):
                raise ValueError("rejection_reason must be empty when status is not REJECTED")
        return self


class DocumentDownloadResponse(BaseModel):
    download_url: str
    expires_in_seconds: int


# ============================================================================
# promo_codes  (management endpoints gated by internal service key — see
# app/security.py::require_internal_service — until a platform-admin role
# exists in `system_role`)
# ============================================================================
class PromoCodeCreate(BaseModel):
    code: str = Field(min_length=3, max_length=64, strip_whitespace=True, pattern=r"^[A-Z0-9_]+$")
    discount_type: DiscountType
    discount_value: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    max_uses: int = Field(gt=0, le=2147483647)
    valid_from: AwareDatetime
    valid_until: AwareDatetime
    is_active: bool = True
    assigned_company_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def validate_promo(self) -> "PromoCodeCreate":
        if self.discount_type == DiscountType.PERCENTAGE and self.discount_value > 100:
            raise ValueError("Percentage discount cannot exceed 100")
        if self.valid_until <= self.valid_from:
            raise ValueError("valid_until must be after valid_from")
        return self


class PromoCodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    discount_type: DiscountType
    discount_value: Decimal
    max_uses: int
    current_uses: int
    valid_from: datetime
    valid_until: datetime
    is_active: bool
    assigned_company_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class PromoCodeValidateResponse(BaseModel):
    valid: bool
    reason: str | None = None
    discount_type: DiscountType | None = None
    discount_value: Decimal | None = None


# ============================================================================
# payments
# ============================================================================
class CheckoutRequest(BaseModel):
    promo_code: str | None = Field(default=None, min_length=3, max_length=64, strip_whitespace=True, pattern=r"^[A-Z0-9_]+$")
    plan_package: PackType | None = None
    plan_tier: int | None = Field(default=None, ge=1, le=4)


class CheckoutResponse(BaseModel):
    payment_id: uuid.UUID
    razorpay_order_id: str
    razorpay_key_id: str
    amount_paid: Decimal
    currency: str


class PaymentVerifyRequest(BaseModel):
    razorpay_order_id: str = Field(min_length=1, strip_whitespace=True)
    razorpay_payment_id: str = Field(min_length=1, strip_whitespace=True)
    razorpay_signature: str = Field(min_length=1, strip_whitespace=True)


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    initiated_by_profile_id: str
    razorpay_order_id: str
    razorpay_payment_id: str | None
    status: PaymentStatus
    original_amount: Decimal
    discount_amount: Decimal
    amount_paid: Decimal
    currency: str
    applied_promo_id: uuid.UUID | None
    plan_package: PackType
    plan_tier: int
    created_at: datetime
    updated_at: datetime


class RefundRequestCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class WalletRechargeRequest(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class RefundRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    payment_id: uuid.UUID
    requested_by_profile_id: str
    amount: Decimal
    status: RefundRequestStatus
    razorpay_refund_id: str | None = None
    actioned_by: str | None = None
    actioned_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


# ============================================================================
# wallet_recharges
# ============================================================================
class WalletRechargeCheckoutRequest(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class WalletRechargeCheckoutResponse(BaseModel):
    recharge_id: uuid.UUID
    razorpay_order_id: str
    razorpay_key_id: str
    amount: Decimal
    currency: str


class WalletRechargeVerifyRequest(BaseModel):
    razorpay_order_id: str = Field(min_length=1, strip_whitespace=True)
    razorpay_payment_id: str = Field(min_length=1, strip_whitespace=True)
    razorpay_signature: str = Field(min_length=1, strip_whitespace=True)


class WalletRechargeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    initiated_by_profile_id: str
    razorpay_order_id: str
    razorpay_payment_id: str | None
    status: WalletRechargeStatus
    amount: Decimal
    currency: str
    created_at: datetime
    updated_at: datetime


class WalletBalanceOut(BaseModel):
    """Lightweight response for wallet balance queries."""
    company_id: uuid.UUID
    wallet_balance: Decimal
    frozen_wallet_balance: Decimal
    available_balance: Decimal  # wallet_balance - frozen_wallet_balance


# ============================================================================
# KPIs
# ============================================================================
class TeamKPIs(BaseModel):
    total_members: int
    active_members: int
    pending_invites: int


class DocumentKPIs(BaseModel):
    total_uploaded: int
    pending_verification: int
    verified: int
    rejected: int


class FinancialKPIs(BaseModel):
    lifetime_spend_inr: Decimal
    total_refunded_inr: Decimal
    net_spend_inr: Decimal


class CompanyDashboardKPIs(BaseModel):
    company_id: uuid.UUID
    pack: PackType
    tier: int
    team: TeamKPIs
    documents: DocumentKPIs
    financials: FinancialKPIs


# ============================================================================
# material_listings
# ============================================================================
class MaterialListingCreate(BaseModel):
    """Payload a Recycler sends when posting a new material deal."""
    material_type: MaterialType
    category: str = Field(min_length=1, max_length=255, strip_whitespace=True)
    grade: str = Field(min_length=1, max_length=127, strip_whitespace=True)
    price_per_unit: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    total_quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    # Optional invoice document (already uploaded via the presign flow).
    # If omitted, the risk evaluator will set validity_risk = "HIGHEST RISK".
    invoice_document_id: uuid.UUID | None = Field(
        default=None,
        description="ID of an already-uploaded document to use as the invoice for this deal.",
    )
    # Manual override for validity_risk — if provided AND no algorithm is running,
    # this value is stored. The evaluator always runs last and may overwrite it.
    validity_risk: str | None = Field(
        default=None,
        max_length=512,
        strip_whitespace=True,
        description="Overridden by the risk evaluator. Leave blank to auto-evaluate.",
    )
    # ── Technical Data Sheet (TDS) Fields ──
    description: str | None = Field(default=None, description="Detailed text description of the material.")
    batch_inspection_report: str | None = Field(default=None, max_length=255)
    min_order_quantity: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    carbon_reduction_per_kg: Decimal | None = Field(default=None, max_digits=12, decimal_places=2)
    water_conservation_per_kg: Decimal | None = Field(default=None, max_digits=12, decimal_places=2)
    accreditations: list[str] = Field(default_factory=list)
    technical_parameters: dict[str, Any] = Field(default_factory=dict)


class MaterialListingUpdate(BaseModel):
    """Partial update — only supplied fields are changed."""
    category: str | None = Field(default=None, min_length=1, max_length=255, strip_whitespace=True)
    grade: str | None = Field(default=None, min_length=1, max_length=127, strip_whitespace=True)
    price_per_unit: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    # total_quantity may only be increased (not decreased below already-sold amount).
    # The endpoint enforces this constraint; schema just validates it's positive.
    total_quantity: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    validity_risk: str | None = Field(default=None, max_length=512, strip_whitespace=True)
    is_active: bool | None = None
    
    # ── Technical Data Sheet (TDS) Fields ──
    description: str | None = None
    batch_inspection_report: str | None = Field(default=None, max_length=255)
    min_order_quantity: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    carbon_reduction_per_kg: Decimal | None = Field(default=None, max_digits=12, decimal_places=2)
    water_conservation_per_kg: Decimal | None = Field(default=None, max_digits=12, decimal_places=2)
    accreditations: list[str] | None = None
    technical_parameters: dict[str, Any] | None = None


class MaterialListingInvoiceAttach(BaseModel):
    """Body for PATCH /{listing_id}/invoice — attach or replace the invoice."""
    invoice_document_id: uuid.UUID = Field(
        description="ID of an already-uploaded document to attach as the invoice."
    )


class MaterialListingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    recycler_id: uuid.UUID | None = None
    created_by_brand_id: uuid.UUID | None = None
    offline_recycler_name: str | None = None
    material_type: MaterialType  # ORM attribute name (maps to 'type' column)
    category: str
    grade: str
    price_per_unit: Decimal
    total_quantity: Decimal
    available_quantity: Decimal
    validity_risk: str | None = None
    invoice_document_id: uuid.UUID | None = None
    is_active: bool
    
    # ── Technical Data Sheet (TDS) Fields ──
    description: str | None = None
    batch_inspection_report: str | None = None
    min_order_quantity: Decimal | None = None
    carbon_reduction_per_kg: Decimal | None = None
    water_conservation_per_kg: Decimal | None = None
    accreditations: list[str] | None = Field(default_factory=list)
    technical_parameters: dict[str, Any] | None = Field(default_factory=dict)
    
    # ── Nested/Joined Fields ──
    recycler_name: str | None = None
    recycler_city: str | None = None
    recycler_state: str | None = None

    created_at: datetime
    updated_at: datetime


# ============================================================================
# brand marketplace purchases
# ============================================================================
class MaterialPurchaseCreate(BaseModel):
    """Payload a Brand sends when buying from a recycler's listing."""
    quantity: Decimal = Field(
        gt=0,
        max_digits=12,
        decimal_places=2,
        description="Amount to purchase. Must not exceed the listing's available_quantity.",
    )
    payment_method: PaymentMethod = Field(
        default=PaymentMethod.DIRECT,
        description="Payment method to use. Defaults to DIRECT."
    )


class ArrivalStatusUpdate(BaseModel):
    arrival_status: ArrivalStatus


class MaterialPurchaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    listing_id: uuid.UUID
    brand_id: uuid.UUID
    category: str
    purchased_quantity: Decimal
    total_price: Decimal
    # Breakdown of wallet impact
    immediate_deduction: Decimal = Decimal("0.00")  # already debited; computed, not stored in ORM
    pending_wallet_deduction: Decimal  # frozen; settled on delivery
    purchase_type: str
    purchase_status: PurchaseStatus
    payment_method: PaymentMethod
    razorpay_order_id: str | None = None
    razorpay_payment_id: str | None = None
    arrival_status: ArrivalStatus
    recycler_name: str | None = None
    brand_name: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm_with_immediate(
        cls,
        purchase: "MaterialPurchaseOut",
        immediate_deduction: Decimal,
    ) -> "MaterialPurchaseOut":
        """Convenience factory — ORM objects don't store immediate_deduction."""
        data = cls.model_validate(purchase)
        data.immediate_deduction = immediate_deduction
        return data


# ============================================================================
# Brand Dashboard KPIs
# ============================================================================
class MaterialPurchaseBreakdownItem(BaseModel):
    material_type: str
    category: str
    total_quantity: Decimal


class MonthlyPurchaseTrendItem(BaseModel):
    month: str  # Format: YYYY-MM
    total_quantity: Decimal
    average_rate: Decimal


class TopRecyclerItem(BaseModel):
    recycler_id: uuid.UUID
    recycler_name: str
    total_quantity: Decimal
    total_value: Decimal



class OrderStatusSummary(BaseModel):
    delivered: int
    shipped: int
    ready_to_ship: int
    processing: int
    pending: int
    canceled: int


class EPRKPIs(BaseModel):
    credits_available: Decimal
    credits_required:  Decimal
    credits_purchased: Decimal
    credits_utilized:  Decimal


class CompanyEPRSetUtilized(BaseModel):
    """Admin-only: set epr_credits_utilized. available is auto-derived as purchased - utilized."""
    epr_credits_utilized: Decimal

    @field_validator("epr_credits_utilized")
    @classmethod
    def must_be_non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("epr_credits_utilized cannot be negative")
        return v


class CompanyEPROverride(BaseModel):
    """Admin-only: directly override all three mutable EPR states."""
    epr_credits_required:  Decimal
    epr_credits_purchased: Decimal
    epr_credits_utilized:  Decimal

    @field_validator("epr_credits_required", "epr_credits_purchased", "epr_credits_utilized")
    @classmethod
    def must_be_non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("EPR credit values cannot be negative")
        return v


class WalletTransactionItem(BaseModel):
    transaction_id: str
    date: datetime
    amount: Decimal
    is_credit: bool
    payment_method: str
    type: str
    status: str

class WalletKPIs(BaseModel):
    current_balance: Decimal
    pending_payments: Decimal
    total_recharge: Decimal
    total_spending: Decimal

class DashboardPurchaseHistoryItem(BaseModel):
    po_id: str
    recycler_name: str
    material_type: str
    quantity: Decimal
    rate: Decimal
    total_value: Decimal
    order_date: datetime
    status: str

class OfflineDealCreate(BaseModel):
    recycler_name: str
    material_type: MaterialType
    category: str
    grade: str
    quantity: Decimal = Field(..., gt=0)
    total_price: Decimal = Field(..., gt=0)
    validity_risk: str | None = None
    invoice_document_id: uuid.UUID | None = None

class DashboardDealInvoiceItem(BaseModel):
    invoice_no: str
    date: datetime
    recycler_name: str
    category: str
    quantity: Decimal
    amount: Decimal
    type: str
    document_url: str | None

class BrandDashboardKPIs(BaseModel):
    company_id: uuid.UUID
    material_purchased_breakdown: list[MaterialPurchaseBreakdownItem]
    wallet_kpis: WalletKPIs
    total_spend_inr: Decimal
    avg_spend_per_mt: Decimal
    epr: EPRKPIs
    unique_recyclers_count: int
    monthly_trend: list[MonthlyPurchaseTrendItem]
    time_filtered_breakdown: list[MaterialPurchaseBreakdownItem]
    top_recyclers: list[TopRecyclerItem]
    order_status_summary: OrderStatusSummary
    recent_purchases: list[DashboardPurchaseHistoryItem]
    wallet_transactions: list[WalletTransactionItem]
    deal_invoices: list[DashboardDealInvoiceItem]
    offline_deals: list[DashboardDealInvoiceItem]


# ============================================================================
# Recycler Dashboard KPIs
# ============================================================================
class InvoiceStatsKPI(BaseModel):
    total_uploaded: int
    approved: int
    pending: int
    rejected: int

class RecyclerMonthlySalesTrendItem(BaseModel):
    month: str
    amount_paid: Decimal
    amount_pending: Decimal


class RecyclerDealStatusSummary(BaseModel):
    pending: int
    processing: int
    ready_to_ship: int
    in_transit: int
    delivered: int
    cancelled: int


class BrandDealBreakdownItem(BaseModel):
    deal_id: str
    buyer_name: str
    buyer_contact_person: str
    buyer_gst_number: str
    buyer_mobile_number: str
    buyer_email: str
    buyer_address: str
    date_of_deal: datetime
    quantity: Decimal
    amount: Decimal
    status: str
    invoice_url: str | None = None


class CollectorDealBreakdownItem(BaseModel):
    id: uuid.UUID
    collector_name: str
    material_type: str
    quantity: Decimal
    price: Decimal
    document_url: str | None = None
    created_at: datetime


class RecyclerDashboardKPIs(BaseModel):
    company_id: uuid.UUID
    monthly_sales_trend: list[RecyclerMonthlySalesTrendItem]
    deal_status_summary: RecyclerDealStatusSummary
    brand_deals_breakdown: list[BrandDealBreakdownItem]
    total_brand_deals_count: int
    collector_deals_breakdown: list[CollectorDealBreakdownItem]
    total_collector_deals_count: int
    total_collector_spend: Decimal


class CollectorSpendCategorySummaryItem(BaseModel):
    category: str
    material_type: str
    total_spend: Decimal
    total_quantity: Decimal


class MonthlyCollectorSpendSummaryItem(BaseModel):
    month: str
    total_spend: Decimal
    breakdown: list[CollectorSpendCategorySummaryItem]


class CollectorSpendSummaryResponse(BaseModel):
    monthly_summaries: list[MonthlyCollectorSpendSummaryItem]


# ============================================================================
# Collector Purchases
# ============================================================================
class CollectorPurchaseCreate(BaseModel):
    collector_name: str = Field(min_length=1, strip_whitespace=True)
    collector_company_name: str = Field(min_length=1, strip_whitespace=True)
    mobile_number: str = Field(min_length=10, max_length=15, strip_whitespace=True)
    gst_number: str | None = None
    address: str = Field(min_length=1, strip_whitespace=True)
    category: MaterialType
    material_type: str = Field(min_length=1, strip_whitespace=True)
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    document_id: uuid.UUID | None = None

class CollectorPurchaseUpdate(BaseModel):
    collector_name: str | None = Field(default=None, min_length=1, strip_whitespace=True)
    collector_company_name: str | None = Field(default=None, min_length=1, strip_whitespace=True)
    mobile_number: str | None = Field(default=None, min_length=10, max_length=15, strip_whitespace=True)
    gst_number: str | None = None
    address: str | None = Field(default=None, min_length=1, strip_whitespace=True)
    category: MaterialType | None = None
    material_type: str | None = Field(default=None, min_length=1, strip_whitespace=True)
    quantity: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    price: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    document_id: uuid.UUID | None = None


class CollectorPurchaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    recycler_id: uuid.UUID
    collector_name: str
    collector_company_name: str
    mobile_number: str
    gst_number: str | None
    address: str
    category: MaterialType
    material_type: str
    quantity: Decimal
    price: Decimal
    document_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


# ============================================================================
# Recycler Financial Reports
# ============================================================================
class RecyclerMonthlyMaterialPurchased(BaseModel):
    category: str
    material_type: str
    total_quantity: Decimal
    total_spend: Decimal


class RecyclerMonthlyMaterialRecycled(BaseModel):
    category: str
    material_type: str
    total_quantity: Decimal


class RecyclerMonthlyReport(BaseModel):
    month: str  # Format: YYYY-MM
    material_purchased_from_collectors: list[RecyclerMonthlyMaterialPurchased]
    material_recycled: list[RecyclerMonthlyMaterialRecycled]
    sales_paid: Decimal
    sales_pending: Decimal
    revenue: Decimal


class RecyclerFinancialReportResponse(BaseModel):
    total_revenue_period: Decimal
    total_sales_period: Decimal
    total_sales_paid: Decimal
    total_sales_pending: Decimal
    total_material_recycled: Decimal
    monthly_reports: list[RecyclerMonthlyReport]


# ============================================================================
# Recycler Wallet Review
# ============================================================================
class RecyclerWalletInvoiceItem(BaseModel):
    invoice_no: str
    company_name: str
    amount: Decimal
    date_of_deal: datetime
    status: str
    invoice_url: str


class RecyclerWalletReview(BaseModel):
    total_payment_received: Decimal
    total_pending_amount: Decimal
    total_invoices_count: int
    invoices: list[RecyclerWalletInvoiceItem]


# ============================================================================
# Recycler Invoice Ledger
# ============================================================================
class InvoiceLedgerItem(BaseModel):
    invoice_no: str
    date: datetime
    supplier: str
    category: str
    qty: Decimal
    rate: Decimal
    total: Decimal
    action_url: str | None
    deal_type: str


class InvoiceLedgerResponse(BaseModel):
    items: list[InvoiceLedgerItem]
    total_count: int


# ============================================================================
# Invoice Proofs & Utility Metrics
# ============================================================================
class InvoiceProofCreate(BaseModel):
    invoice_id: uuid.UUID
    document_name: str
    category: InvoiceProofCategory
    period: str
    unit_consumed: Decimal = Decimal("0.00")
    amount_spent: Decimal = Decimal("0.00")
    total_amount_used: Decimal = Decimal("0.00")
    total_amount_recycled: Decimal = Decimal("0.00")
    document_id: uuid.UUID | None = None


class InvoiceProofUpdate(BaseModel):
    document_name: str | None = None
    category: InvoiceProofCategory | None = None
    period: str | None = None
    unit_consumed: Decimal | None = None
    amount_spent: Decimal | None = None
    total_amount_used: Decimal | None = None
    total_amount_recycled: Decimal | None = None
    document_id: uuid.UUID | None = None


class InvoiceProofOut(BaseModel):
    id: uuid.UUID
    invoice_id: uuid.UUID
    document_name: str
    category: InvoiceProofCategory
    period: str
    unit_consumed: Decimal
    amount_spent: Decimal
    total_amount_used: Decimal
    total_amount_recycled: Decimal
    document_id: uuid.UUID | None = None
    document_url: str | None = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class InvoiceProofListResponse(BaseModel):
    items: list[InvoiceProofOut]
    total_count: int


class UtilityMetricsKPIs(BaseModel):
    energy_output_ratio: Decimal
    waybill_verified_scrap: Decimal
    recorded_utility_invoices: Decimal
    verified_proof_files: int


# ============================================================================
# Advanced Search Filters
# ============================================================================

class MarketplaceSearchFilter(BaseModel):
    """
    Advanced search filters for the Brand Marketplace listing browse endpoint.
    All fields are optional — any combination may be supplied simultaneously.
    """
    # ── Material & Category ───────────────────────────────────────────────────
    material_type: MaterialType | None = Field(default=None, description="Exact match on material type (PLASTIC / METAL / BOTH).")
    category: str | None = Field(default=None, description="Substring (case-insensitive) search on listing category.")
    grade: str | None = Field(default=None, description="Substring (case-insensitive) search on material grade.")

    # ── Purity (from technical_parameters JSONB) ──────────────────────────────
    min_purity: Decimal | None = Field(default=None, ge=0, le=100, description="Minimum purity % stored in technical_parameters->>'purity'.")
    max_purity: Decimal | None = Field(default=None, ge=0, le=100, description="Maximum purity % stored in technical_parameters->>'purity'.")

    # ── Price Range ───────────────────────────────────────────────────────────
    min_price: Decimal | None = Field(default=None, ge=0, description="Minimum price per unit (₹).")
    max_price: Decimal | None = Field(default=None, ge=0, description="Maximum price per unit (₹).")

    # ── Volume / Availability ─────────────────────────────────────────────────
    min_quantity: Decimal | None = Field(default=None, ge=0, description="Minimum available_quantity required.")

    # ── Certifications / Accreditations ──────────────────────────────────────
    certifications: list[str] | None = Field(default=None, description="List of required accreditation strings. Listings must possess ALL of them.")

    # ── Recycler / Location ───────────────────────────────────────────────────
    recycler_id: uuid.UUID | None = Field(default=None, description="Filter to a specific recycler company ID.")
    state: str | None = Field(default=None, description="Substring search on recycler state.")
    city: str | None = Field(default=None, description="Substring search on recycler city.")
    min_esg_rating: int | None = Field(default=None, ge=0, le=100, description="Minimum ESG rating of the recycler company.")

    # ── Sorting ───────────────────────────────────────────────────────────────
    sort_by: Literal["price_asc", "price_desc", "carbon_desc", "date_desc", "recommended"] = Field(
        default="date_desc",
        description=(
            "Sorting strategy. 'recommended' requires the brand's remaining EPR credits "
            "(epr_credits_required - epr_credits_purchased) to rank listings that best "
            "fulfill the deficit first."
        ),
    )

    # ── Pagination ────────────────────────────────────────────────────────────
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_price_range(self) -> "MarketplaceSearchFilter":
        if self.min_price is not None and self.max_price is not None:
            if self.min_price > self.max_price:
                raise ValueError("min_price must be <= max_price")
        if self.min_purity is not None and self.max_purity is not None:
            if self.min_purity > self.max_purity:
                raise ValueError("min_purity must be <= max_purity")
        return self


class BrandPurchasedFromFilter(BaseModel):
    """
    Filter/search for the 'Purchased From' supplier directory visible to Brands.
    Returns the distinct recycler companies from whom the brand has made purchases.
    """
    name: str | None = Field(default=None, description="Substring (case-insensitive) search on recycler company name.")
    state: str | None = Field(default=None, description="Substring search on recycler state.")
    city: str | None = Field(default=None, description="Substring search on recycler city.")
    material: MaterialType | None = Field(default=None, description="Exact match on recycler company material type.")

    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class BrandPurchaseFilter(BaseModel):
    """
    Advanced filter for a Brand's own purchase orders.
    Covers both the Delivery Tracking view and the Purchased Invoices view.
    All fields are optional and fully combinable.
    """
    # ── Status Filters ────────────────────────────────────────────────────────
    purchase_status: PurchaseStatus | None = Field(default=None, description="Filter by purchase lifecycle status.")
    arrival_status: ArrivalStatus | None = Field(default=None, description="Filter by delivery / arrival status.")

    # ── Financial ─────────────────────────────────────────────────────────────
    payment_method: PaymentMethod | None = Field(default=None, description="Filter by payment method (WALLET / DIRECT).")
    min_amount: Decimal | None = Field(default=None, ge=0, description="Minimum total_price (₹).")
    max_amount: Decimal | None = Field(default=None, ge=0, description="Maximum total_price (₹).")

    # ── Search ────────────────────────────────────────────────────────────────
    category: str | None = Field(default=None, description="Substring search on purchase category.")
    recycler_name: str | None = Field(default=None, description="Substring search on the seller recycler company name.")

    # ── Date Range ────────────────────────────────────────────────────────────
    start_date: datetime | None = Field(default=None, description="Filter purchases created on or after this datetime (UTC).")
    end_date: datetime | None = Field(default=None, description="Filter purchases created on or before this datetime (UTC).")

    # ── Sorting ───────────────────────────────────────────────────────────────
    sort_by: Literal["date_desc", "date_asc", "amount_desc", "amount_asc"] = Field(default="date_desc")

    # ── Pagination ────────────────────────────────────────────────────────────
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_ranges(self) -> "BrandPurchaseFilter":
        if self.min_amount is not None and self.max_amount is not None:
            if self.min_amount > self.max_amount:
                raise ValueError("min_amount must be <= max_amount")
        if self.start_date is not None and self.end_date is not None:
            if self.start_date > self.end_date:
                raise ValueError("start_date must be before end_date")
        return self


class CollectorPurchaseFilter(BaseModel):
    """
    Advanced filter for the Recycler's Collector Purchases section.
    All fields are optional and fully combinable.
    """
    # ── Collector Search ──────────────────────────────────────────────────────
    collector_name: str | None = Field(default=None, description="Substring (case-insensitive) search on collector_name.")
    collector_company_name: str | None = Field(default=None, description="Substring search on collector_company_name.")

    # ── Material ──────────────────────────────────────────────────────────────
    category: MaterialType | None = Field(default=None, description="Exact match on material category enum (PLASTIC/METAL/BOTH).")
    material_type: str | None = Field(default=None, description="Substring search on the free-text material_type field.")

    # ── Financial ─────────────────────────────────────────────────────────────
    min_amount: Decimal | None = Field(default=None, ge=0, description="Minimum purchase price (₹).")
    max_amount: Decimal | None = Field(default=None, ge=0, description="Maximum purchase price (₹).")

    # ── Date Range ────────────────────────────────────────────────────────────
    start_date: datetime | None = Field(default=None, description="Filter records created on or after this datetime.")
    end_date: datetime | None = Field(default=None, description="Filter records created on or before this datetime.")

    # ── Sorting ───────────────────────────────────────────────────────────────
    sort_by: Literal["date_desc", "date_asc", "amount_desc", "amount_asc"] = Field(default="date_desc")

    # ── Pagination ────────────────────────────────────────────────────────────
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_ranges(self) -> "CollectorPurchaseFilter":
        if self.min_amount is not None and self.max_amount is not None:
            if self.min_amount > self.max_amount:
                raise ValueError("min_amount must be <= max_amount")
        if self.start_date is not None and self.end_date is not None:
            if self.start_date > self.end_date:
                raise ValueError("start_date must be before end_date")
        return self


class InvoiceProofFilter(BaseModel):
    """
    Advanced filter for the Recycler's Track Invoices section (InvoiceProofs).
    All fields are optional and fully combinable.
    """
    # ── Category ──────────────────────────────────────────────────────────────
    category: InvoiceProofCategory | None = Field(default=None, description="Filter by invoice proof category (ELECTRICITY/WATER/LOGISTICS/FUEL).")

    # ── Search Term ───────────────────────────────────────────────────────────
    document_name: str | None = Field(default=None, description="Substring (case-insensitive) search on document_name.")
    period: str | None = Field(default=None, description="Substring search on the period string (e.g. '2024-01').")

    # ── Financial Ranges ──────────────────────────────────────────────────────
    min_amount_spent: Decimal | None = Field(default=None, ge=0, description="Minimum amount_spent (₹).")
    max_amount_spent: Decimal | None = Field(default=None, ge=0, description="Maximum amount_spent (₹).")
    min_total_amount_used: Decimal | None = Field(default=None, ge=0, description="Minimum total_amount_used.")
    max_total_amount_used: Decimal | None = Field(default=None, ge=0, description="Maximum total_amount_used.")

    # ── Date Range (upload date) ──────────────────────────────────────────────
    start_date: datetime | None = Field(default=None, description="Filter records created on or after this datetime.")
    end_date: datetime | None = Field(default=None, description="Filter records created on or before this datetime.")

    # ── Sorting ───────────────────────────────────────────────────────────────
    sort_by: Literal["date_desc", "date_asc", "amount_desc", "amount_asc"] = Field(default="date_desc")

    # ── Pagination ────────────────────────────────────────────────────────────
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_ranges(self) -> "InvoiceProofFilter":
        if self.min_amount_spent is not None and self.max_amount_spent is not None:
            if self.min_amount_spent > self.max_amount_spent:
                raise ValueError("min_amount_spent must be <= max_amount_spent")
        if self.start_date is not None and self.end_date is not None:
            if self.start_date > self.end_date:
                raise ValueError("start_date must be before end_date")
        return self


# ============================================================================
# Marketplace Overview
# ============================================================================
class MarketplaceOverviewStats(BaseModel):
    total_volume_available: Decimal
    total_active_listings: int
    avg_price_plastic: Decimal
    avg_price_metal: Decimal
    total_recyclers: int


# ============================================================================
# Withdrawals
# ============================================================================

class BankAccountCreate(BaseModel):
    """Create a new bank account or UPI payout destination.
    Either (account_number + ifsc_code + beneficiary_name) or upi_id must be provided.
    """
    beneficiary_name: str | None = None
    account_number: str | None = None
    ifsc_code: str | None = None
    upi_id: str | None = None

    @model_validator(mode="after")
    def check_bank_or_upi(self) -> "BankAccountCreate":
        has_bank = (
            self.account_number is not None
            and self.ifsc_code is not None
            and self.beneficiary_name is not None
        )
        has_upi = self.upi_id is not None
        if not has_bank and not has_upi:
            raise ValueError(
                "Provide either (beneficiary_name + account_number + ifsc_code) for bank transfer, "
                "or upi_id for UPI transfer."
            )
        return self


class BankAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    beneficiary_name: str | None = None
    account_number: str | None = None
    ifsc_code: str | None = None
    upi_id: str | None = None
    created_at: datetime


class WithdrawalRequestCreate(BaseModel):
    bank_account_id: uuid.UUID
    amount: Decimal = Field(gt=0, description="Amount to withdraw in INR")


class WithdrawalRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    bank_account_id: uuid.UUID
    amount: Decimal
    status: WithdrawalStatus
    transaction_reference: str | None = None
    actioned_by: str | None = None
    actioned_at: datetime | None = None
    created_at: datetime


class WithdrawalApproveRequest(BaseModel):
    """Body required when an admin manually approves a withdrawal."""
    transaction_reference: str = Field(
        min_length=3,
        description="UTR number, UPI transaction ID, or other reference for the manual payment",
    )
