"""
Fixed, backend-only pricing. The frontend only ever sends which
(package, tier) a company is on — never an amount. This is the single
source of truth for what that combination costs.

NOTE: these numbers are PLACEHOLDERS. Replace with real pricing before
going live. Amounts are in INR (rupees); conversion to paise happens in
app/services/razorpay_client.py right before calling Razorpay.
"""

from fastapi import HTTPException
from app.models import PackType

PRICING_MATRIX: dict[tuple[PackType, int], float] = {
    # Tier 1 (< 100 MT/year)
    (PackType.STARTER, 1): 45_000,
    (PackType.GROWTH, 1): 95_000,
    (PackType.ENTERPRISE, 1): 160_000,
    
    # Tier 2 (100–500 MT/year)
    (PackType.STARTER, 2): 85_000,
    (PackType.GROWTH, 2): 180_000,
    (PackType.ENTERPRISE, 2): 320_000,
    
    # Tier 3 (500–2,000 MT/year)
    (PackType.STARTER, 3): 150_000,
    (PackType.GROWTH, 3): 310_000,
    (PackType.ENTERPRISE, 3): 550_000,
}


def get_price_for(pack: PackType, tier: int) -> float:
    if tier == 4:
        raise HTTPException(
            status_code=400, 
            detail="Tier 4 (> 2,000 MT/year) requires custom enterprise pricing. Please contact sales to upgrade."
        )
        
    key = (pack, tier)
    if key not in PRICING_MATRIX:
        raise ValueError(f"No price configured for pack={pack.value} tier={tier}")
    return PRICING_MATRIX[key]
