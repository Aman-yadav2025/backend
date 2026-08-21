import enum
import uuid
from datetime import datetime

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
    RECYCLING_MANIFEST = "RECYCLING_MANIFEST"
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


class CompanyType(str, enum.Enum):
    BRAND = "BRAND"
    RECYCLER = "RECYCLER"


class PackType(str, enum.Enum):
    STARTER = "STARTER"
    GROWTH = "GROWTH"
    ENTERPRISE = "ENTERPRISE"


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
    gst_number: Mapped[str | None] = mapped_column(Text)
    contact_person_name: Mapped[str | None] = mapped_column(Text)
    contact_person_email: Mapped[str | None] = mapped_column(Text)
    company_type: Mapped[CompanyType] = mapped_column(_pg_enum(CompanyType, "company_type"), nullable=False)
    pack: Mapped[PackType] = mapped_column(_pg_enum(PackType, "pack_type"), nullable=False)
    tier: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("tier between 1 and 4", name="chk_company_tier_range"),
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

