from decimal import Decimal
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import MaterialListing, MaterialType
from app.schemas import MarketplaceOverviewStats

router = APIRouter(prefix="/marketplace-overview", tags=["Marketplace Overview"])


@router.get("/", response_model=MarketplaceOverviewStats)
async def get_marketplace_overview(db: AsyncSession = Depends(get_db)):
    """
    Returns aggregate statistics for the marketplace home page:
    - total volume available
    - total active listings
    - avg price of plastic material
    - avg price of metal material
    - total number of recyclers offering active listings
    """
    
    # We aggregate over all active listings that have at least some available quantity.
    query = select(
        func.coalesce(func.sum(MaterialListing.available_quantity), Decimal("0.00")).label("total_volume"),
        func.count(MaterialListing.id).label("total_listings"),
        func.count(func.distinct(MaterialListing.recycler_id)).label("total_recyclers"),
        func.coalesce(
            func.avg(
                case(
                    (MaterialListing.material_type == MaterialType.PLASTIC, MaterialListing.price_per_unit),
                    else_=None
                )
            ), Decimal("0.00")
        ).label("avg_plastic"),
        func.coalesce(
            func.avg(
                case(
                    (MaterialListing.material_type == MaterialType.METAL, MaterialListing.price_per_unit),
                    else_=None
                )
            ), Decimal("0.00")
        ).label("avg_metal")
    ).where(
        MaterialListing.is_active == True,
        MaterialListing.available_quantity > 0
    )

    result = await db.execute(query)
    row = result.one()

    return MarketplaceOverviewStats(
        total_volume_available=row.total_volume,
        total_active_listings=row.total_listings,
        avg_price_plastic=row.avg_plastic,
        avg_price_metal=row.avg_metal,
        total_recyclers=row.total_recyclers
    )
