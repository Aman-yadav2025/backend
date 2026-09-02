import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as PgEnum,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    Index,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


# ============================================================================
# Enums — names/values must match the Postgres enum types created in
# migrations/001_initial_schema.sql and 002_add_company_plan_fields.sql
# ============================================================================
class SystemRole(str, enum.Enum):
    RECYCLER = "RECYCLER"
    BRAND_ADMIN = "BRAND_ADMIN"
    BRAND_EMPLOYEE = "BRAND_EMPLOYEE"
    PLATFORM_ADMIN = "PLATFORM_ADMIN"


class MemberRole(str, enum.Enum):
    OWNER = "OWNER"
    MEMBER = "MEMBER"


class MemberStatus(str, enum.Enum):
    INVITED = "INVITED"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    TERMINATED = "TERMINATED"
    DELETING = "DELETING"


class DocumentCategory(str, enum.Enum):
    COMPLIANCE = "COMPLIANCE"
    TAX = "TAX"
    GST_CERTIFICATE = "GST_CERTIFICATE"
    PAN_CARD = "PAN_CARD"
    FACTORY_LICENSE = "FACTORY_LICENSE"
    CERTIFICATE_OF_INCORPORATION = "CERTIFICATE_OF_INCORPORATION"
    EPR_CERTIFICATE = "EPR_CERTIFICATE"
    CANCELLED_CHEQUE = "CANCELLED_CHEQUE"
    RECYCLING_MANIFEST = "RECYCLING_MANIFEST"
    COLLECTOR_RECEIPT = "COLLECTOR_RECEIPT"
    OTHER = "OTHER"


class DocumentStatus(str, enum.Enum):
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class DiscountType(str, enum.Enum):
    PERCENTAGE = "PERCENTAGE"
    FIXED_AMOUNT = "FIXED_AMOUNT"


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PENDING_REFUND = "PENDING_REFUND"
    REFUNDED = "REFUNDED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"


class RefundRequestStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class WalletRechargeStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class MaterialType(str, enum.Enum):
    METAL = "METAL"
    PLASTIC = "PLASTIC"
    BOTH = "BOTH"


class PurchaseStatus(str, enum.Enum):
    PENDING = "PENDING"
    AWAITING_PAYMENT = "AWAITING_PAYMENT"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class ArrivalStatus(str, enum.Enum):
    PENDING = "PENDING"
    READY_TO_SHIP = "READY_TO_SHIP"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"


class CompanyType(str, enum.Enum):
    BRAND = "BRAND"
    RECYCLER = "RECYCLER"


class PaymentMethod(str, enum.Enum):
    WALLET = "WALLET"
    DIRECT = "DIRECT"


class PackType(str, enum.Enum):
    STARTER = "STARTER"
    GROWTH = "GROWTH"
    ENTERPRISE = "ENTERPRISE"


class InvoiceProofCategory(str, enum.Enum):
    ELECTRICITY = "ELECTRICITY"
    WATER = "WATER"
    LOGISTICS = "LOGISTICS"
    FUEL = "FUEL"


def _pg_enum(py_enum: type[enum.Enum], name: str) -> PgEnum:
    # create_type=False: the enum type is created by the SQL migrations,
    # not by SQLAlchemy metadata.create_all().
    return PgEnum(py_enum, name=name, create_type=False, values_callable=lambda e: [m.value for m in e])


# ============================================================================
# Models
# ============================================================================
class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(Text, primary_key=True)  # Clerk user id
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    system_role: Mapped[SystemRole] = mapped_column(_pg_enum(SystemRole, "system_role"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    # Clerk Organization id (e.g. "org_2abc..."). Kept separate from `id`
    # because Clerk org ids are strings, not UUIDs, and every other table's
    # FKs already point at the UUID `id`.
    clerk_org_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    owner_id: Mapped[str] = mapped_column(
        Text, ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    company_email: Mapped[str] = mapped_column(Text, nullable=False)
    mobile_number: Mapped[str] = mapped_column(Text, nullable=False)
    gst_number: Mapped[str] = mapped_column(Text, nullable=False)
    company_pan_number: Mapped[str] = mapped_column(Text, nullable=False)
    factory_address: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str] = mapped_column(Text, nullable=False)
    pincode: Mapped[str] = mapped_column(Text, nullable=False)
    company_website: Mapped[str | None] = mapped_column(Text)
    contact_person_name: Mapped[str] = mapped_column(Text, nullable=False)
    contact_person_email: Mapped[str | None] = mapped_column(Text)
    designation: Mapped[str] = mapped_column(Text, nullable=False)
    material: Mapped[MaterialType] = mapped_column(_pg_enum(MaterialType, "material_type"), nullable=False)
    company_type: Mapped[CompanyType] = mapped_column(_pg_enum(CompanyType, "company_type"), nullable=False)
    pack: Mapped[PackType] = mapped_column(_pg_enum(PackType, "pack_type"), nullable=False)
    tier: Mapped[int] = mapped_column(Integer, nullable=False)
    epr_credits_available:  Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    epr_credits_required:   Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    epr_credits_purchased:  Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    epr_credits_utilized:   Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    wallet_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0.00, nullable=False)
    # Sum of pending second-half amounts across all PENDING marketplace purchases.
    # True spendable balance = wallet_balance - frozen_wallet_balance.
    frozen_wallet_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0.00, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("tier between 1 and 4", name="chk_company_tier_range"),
        CheckConstraint("wallet_balance >= 0", name="chk_company_wallet_balance_positive"),
        CheckConstraint("frozen_wallet_balance >= 0", name="chk_company_frozen_wallet_balance_positive"),
        CheckConstraint("epr_credits_required >= 0",   name="chk_company_epr_credits_required_positive"),
        CheckConstraint("epr_credits_available >= 0",  name="chk_company_epr_credits_available_positive"),
        CheckConstraint("epr_credits_purchased >= 0",  name="chk_company_epr_credits_purchased_positive"),
        CheckConstraint("epr_credits_utilized >= 0",   name="chk_company_epr_credits_utilized_positive"),
        Index("ix_companies_owner_id_unique", "owner_id", unique=True, postgresql_where=text("deleted_at IS NULL")),
    )


class CompanyMember(Base):
    __tablename__ = "company_members"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    profile_id: Mapped[str] = mapped_column(Text, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    member_role: Mapped[MemberRole] = mapped_column(
        _pg_enum(MemberRole, "member_role"), default=MemberRole.MEMBER, nullable=False
    )
    status: Mapped[MemberStatus] = mapped_column(
        _pg_enum(MemberStatus, "member_status"), default=MemberStatus.INVITED, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (UniqueConstraint("company_id", "profile_id", name="uq_company_profile"),)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    uploaded_by_profile_id: Mapped[str] = mapped_column(
        Text, ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=False
    )
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_type: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[DocumentCategory] = mapped_column(
        _pg_enum(DocumentCategory, "document_category"), default=DocumentCategory.OTHER, nullable=False
    )
    status: Mapped[DocumentStatus] = mapped_column(
        _pg_enum(DocumentStatus, "document_status"),
        default=DocumentStatus.PENDING_VERIFICATION,
        nullable=False,
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    verified_by: Mapped[str | None] = mapped_column(Text, ForeignKey("profiles.id", ondelete="RESTRICT"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PromoCode(Base):
    __tablename__ = "promo_codes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    discount_type: Mapped[DiscountType] = mapped_column(_pg_enum(DiscountType, "discount_type"), nullable=False)
    discount_value: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    max_uses: Mapped[int] = mapped_column(Integer, nullable=False)
    current_uses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    assigned_company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    initiated_by_profile_id: Mapped[str] = mapped_column(
        Text, ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=False
    )
    razorpay_order_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    razorpay_payment_id: Mapped[str | None] = mapped_column(Text)
    razorpay_signature: Mapped[str | None] = mapped_column(Text)
    status: Mapped[PaymentStatus] = mapped_column(
        _pg_enum(PaymentStatus, "payment_status"), default=PaymentStatus.PENDING, nullable=False
    )
    original_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    discount_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    amount_paid: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(Text, default="INR", nullable=False)
    applied_promo_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("promo_codes.id", ondelete="SET NULL")
    )
    # Snapshot of what was purchased — companies.pack/tier can change later,
    # this must not drift with it.
    plan_package: Mapped[PackType] = mapped_column(_pg_enum(PackType, "pack_type"), nullable=False)
    plan_tier: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (CheckConstraint("plan_tier between 1 and 4", name="chk_payment_plan_tier_range"),)


class RefundRequest(Base):
    __tablename__ = "refund_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id", ondelete="RESTRICT"), nullable=False
    )
    requested_by_profile_id: Mapped[str] = mapped_column(
        Text, ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=False
    )
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[RefundRequestStatus] = mapped_column(
        _pg_enum(RefundRequestStatus, "refund_request_status"), default=RefundRequestStatus.PENDING, nullable=False
    )
    razorpay_refund_id: Mapped[str | None] = mapped_column(Text, unique=True)
    actioned_by: Mapped[str | None] = mapped_column(Text, ForeignKey("profiles.id", ondelete="RESTRICT"))
    actioned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MaterialListing(Base):
    __tablename__ = "material_listings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    recycler_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=True
    )
    created_by_brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=True
    )
    offline_recycler_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    material_type: Mapped[MaterialType] = mapped_column("type", _pg_enum(MaterialType, "material_type"), nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    grade: Mapped[str] = mapped_column(Text, nullable=False)
    price_per_unit: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    available_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    validity_risk: Mapped[str | None] = mapped_column(Text)
    # Nullable FK to the invoice document. NULL → no invoice → HIGHEST RISK.
    # ON DELETE SET NULL: if the document is deleted, the listing is not
    # destroyed but its risk score must be re-evaluated.
    invoice_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("price_per_unit > 0", name="chk_price_per_unit_positive"),
        CheckConstraint("total_quantity > 0", name="chk_total_quantity_positive"),
        CheckConstraint("available_quantity >= 0 AND available_quantity <= total_quantity", name="chk_available_quantity"),
        Index("idx_material_listings_active", "is_active", postgresql_where=text("is_active = true")),
    )


class MaterialPurchase(Base):
    __tablename__ = "material_purchases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("material_listings.id", ondelete="RESTRICT"), nullable=False
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    category: Mapped[str] = mapped_column(Text, nullable=False)
    purchased_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    purchase_type: Mapped[str] = mapped_column(Text, nullable=False)
    purchase_status: Mapped[PurchaseStatus] = mapped_column(
        _pg_enum(PurchaseStatus, "purchase_status"), default=PurchaseStatus.PENDING, nullable=False
    )
    payment_method: Mapped[PaymentMethod] = mapped_column(
        _pg_enum(PaymentMethod, "payment_method"), default=PaymentMethod.WALLET, nullable=False
    )
    razorpay_order_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    razorpay_payment_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    arrival_status: Mapped[ArrivalStatus] = mapped_column(
        _pg_enum(ArrivalStatus, "arrival_status"), default=ArrivalStatus.PENDING, nullable=False
    )
    # Second-half payment frozen in company.frozen_wallet_balance at purchase time.
    # Deducted from wallet_balance on delivery confirmation; zeroed on CONFIRMED or CANCELLED.
    pending_wallet_deduction: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


    __table_args__ = (
        CheckConstraint("purchased_quantity > 0", name="chk_purchased_quantity_positive"),
        CheckConstraint("total_price > 0", name="chk_total_price_positive"),
        CheckConstraint("pending_wallet_deduction >= 0", name="chk_pending_wallet_deduction_non_negative"),
    )


class WalletRecharge(Base):
    """
    Tracks a Razorpay-backed wallet top-up for a Brand company.
    State machine: PENDING → SUCCESS (wallet credited) or FAILED.
    """
    __tablename__ = "wallet_recharges"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    initiated_by_profile_id: Mapped[str] = mapped_column(
        Text, ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=False
    )
    razorpay_order_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    razorpay_payment_id: Mapped[str | None] = mapped_column(Text)
    razorpay_signature: Mapped[str | None] = mapped_column(Text)
    # Stored as plain text to match the migration's text column with a CHECK constraint.
    status: Mapped[str] = mapped_column(Text, default=WalletRechargeStatus.PENDING.value, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False, default="INR")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("amount > 0", name="chk_wallet_recharge_amount_positive"),
    )


class CollectorPurchase(Base):
    __tablename__ = "collector_purchases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    recycler_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    # NULL for legacy rows created before migration 021 — treated as owner-only editable.
    created_by_profile_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=True
    )
    collector_name: Mapped[str] = mapped_column(Text, nullable=False)
    collector_company_name: Mapped[str] = mapped_column(Text, nullable=False)
    mobile_number: Mapped[str] = mapped_column(Text, nullable=False)
    gst_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[MaterialType] = mapped_column("category", _pg_enum(MaterialType, "material_type"), nullable=False)
    material_type: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_collector_quantity_positive"),
        CheckConstraint("price > 0", name="chk_collector_price_positive"),
        Index("idx_collector_purchases_recycler_id", "recycler_id"),
    )


class InvoiceProof(Base):
    __tablename__ = "invoice_proofs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    recycler_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("collector_purchases.id", ondelete="RESTRICT"), nullable=False
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    document_name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[InvoiceProofCategory] = mapped_column(
        _pg_enum(InvoiceProofCategory, "invoice_proof_category"), nullable=False
    )
    period: Mapped[str] = mapped_column(Text, nullable=False)
    unit_consumed: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    amount_spent: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    total_amount_used: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    total_amount_recycled: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_invoice_proofs_recycler_id", "recycler_id"),
        Index("idx_invoice_proofs_invoice_id", "invoice_id"),
    )
