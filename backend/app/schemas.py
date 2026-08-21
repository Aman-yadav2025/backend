import uuid
from datetime import datetime
from decimal import Decimal

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models import (
    CompanyType,
    DiscountType,
    DocumentCategory,
    DocumentStatus,
    MemberRole,
    MemberStatus,
    PackType,
    PaymentStatus,
    RefundRequestStatus,
    SystemRole,
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
    gst_number: str | None
    contact_person_name: str | None
    contact_person_email: str | None
    company_type: CompanyType
    pack: PackType
    tier: int
    created_at: datetime
    updated_at: datetime


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
    gst_number: str | None = Field(default=None, min_length=1, max_length=127, strip_whitespace=True)
    contact_person_name: str | None = Field(default=None, min_length=1, max_length=255, strip_whitespace=True)
    contact_person_email: EmailStr | None = Field(default=None)

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
        ext = ""
        if "." in self.file_name:
            ext = self.file_name[self.file_name.rindex("."):].lower()
        if ext not in ALLOWED_EXTENSIONS or self.file_type not in ALLOWED_MIME_TYPES:
            raise ValueError("File type not allowed. Allowed types are: PDF, JPG, PNG, DOCX, XLSX")
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
        ext = ""
        if "." in self.file_name:
            ext = self.file_name[self.file_name.rindex("."):].lower()
        if ext not in ALLOWED_EXTENSIONS or self.file_type not in ALLOWED_MIME_TYPES:
            raise ValueError("File type not allowed. Allowed types are: PDF, JPG, PNG, DOCX, XLSX")
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
