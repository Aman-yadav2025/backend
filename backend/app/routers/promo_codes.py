import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import CompanyMember, PromoCode
from app.schemas import PromoCodeCreate, PromoCodeOut, PromoCodeValidateResponse
from app.security import require_active_company_membership, require_platform_admin

router = APIRouter(tags=["promo-codes"])


@router.get("/companies/{company_id}/promo-codes/validate", response_model=PromoCodeValidateResponse)
async def validate_promo_code(
    company_id: uuid.UUID,
    code: str,
    _membership: CompanyMember = Depends(require_active_company_membership),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(PromoCode).where(PromoCode.code == code))
    promo = result.scalar_one_or_none()

    if promo is None:
        return PromoCodeValidateResponse(valid=False, reason="Code does not exist")
    if promo.assigned_company_id is not None and promo.assigned_company_id != company_id:
        return PromoCodeValidateResponse(valid=False, reason="Code is not valid for this company")
    if not promo.is_active:
        return PromoCodeValidateResponse(valid=False, reason="Code is not active")

    now = datetime.now(timezone.utc)
    if now < promo.valid_from or now > promo.valid_until:
        return PromoCodeValidateResponse(valid=False, reason="Code is outside its valid date range")
    if promo.current_uses >= promo.max_uses:
        return PromoCodeValidateResponse(valid=False, reason="Code has reached its usage limit")

    return PromoCodeValidateResponse(
        valid=True,
        discount_type=promo.discount_type,
        discount_value=promo.discount_value,
    )


# ============================================================================
# Management endpoints — gated by PLATFORM_ADMIN.
# ============================================================================
@router.post("/admin/promo-codes", response_model=PromoCodeOut, status_code=201, dependencies=[Depends(require_platform_admin)])
async def create_promo_code(body: PromoCodeCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(PromoCode).where(PromoCode.code == body.code))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Promo code already exists")

    promo = PromoCode(**body.model_dump())
    db.add(promo)
    await db.commit()
    await db.refresh(promo)
    return promo


@router.get("/admin/promo-codes", response_model=list[PromoCodeOut], dependencies=[Depends(require_platform_admin)])
async def list_promo_codes(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PromoCode))
    return result.scalars().all()


@router.patch("/admin/promo-codes/{promo_id}/deactivate", response_model=PromoCodeOut, dependencies=[Depends(require_platform_admin)])
async def deactivate_promo_code(promo_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PromoCode).where(PromoCode.id == promo_id).with_for_update())
    promo = result.scalar_one_or_none()
    if promo is None:
        raise HTTPException(status_code=404, detail="Promo code not found")
    promo.is_active = False
    await db.commit()
    await db.refresh(promo)
    return promo
