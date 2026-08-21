"""
Fixed, backend-only pricing. The frontend only ever sends which
(package, tier) a company is on — never an amount. This is the single
source of truth for what that combination costs.

NOTE: these numbers are PLACEHOLDERS. Replace with real pricing before
going live. Amounts are in INR (rupees); conversion to paise happens in
app/services/razorpay_client.py right before calling Razorpay.
"""

from app.models import PackType

PRICING_MATRIX: dict[tuple[PackType, int], float] = {
    (PackType.STARTER, 1): 4_999,
    (PackType.STARTER, 2): 7_999,
    (PackType.STARTER, 3): 10_999,
    (PackType.STARTER, 4): 13_999,
    (PackType.GROWTH, 1): 19_999,
    (PackType.GROWTH, 2): 24_999,
    (PackType.GROWTH, 3): 29_999,
    (PackType.GROWTH, 4): 34_999,
    (PackType.ENTERPRISE, 1): 49_999,
    (PackType.ENTERPRISE, 2): 69_999,
    (PackType.ENTERPRISE, 3): 89_999,
    (PackType.ENTERPRISE, 4): 119_999,
}


def get_price_for(pack: PackType, tier: int) -> float:
    key = (pack, tier)
    if key not in PRICING_MATRIX:
        raise ValueError(f"No price configured for pack={pack.value} tier={tier}")
    return PRICING_MATRIX[key]
