"""
Risk Evaluator Service
======================
This module is the designated integration point for the risk-scoring algorithm
that automatically evaluates the validity/risk factor of a MaterialListing.

CURRENT BEHAVIOUR
-----------------
- No invoice attached  →  validity_risk = "HIGHEST RISK"  (always enforced)
- Invoice attached      →  returns None (no-op until full algorithm is implemented)

HOW TO PLUG IN THE FULL ALGORITHM
------------------------------------
1. Implement your scoring logic inside `evaluate_listing_risk()` in the
   section marked "PLUG YOUR ALGORITHM IN HERE".
2. The `create_listing` and `attach_invoice` endpoints in
   `routers/marketplace.py` already call `evaluate_listing_risk` — no other
   file needs to change.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import MaterialListing

# Risk level constants — used by both the evaluator and tests.
RISK_HIGHEST = "HIGHEST RISK"
RISK_HIGH    = "HIGH RISK"
RISK_MEDIUM  = "MEDIUM RISK"
RISK_LOW     = "LOW RISK"


async def evaluate_listing_risk(listing: "MaterialListing") -> str:
    """
    Compute and return a risk/validity string for the given listing.

    This function is called:
      - After a new listing is created (with or without an invoice).
      - After an invoice is attached to an existing listing via
        `PATCH /companies/{id}/listings/{lid}/invoice`.

    Args:
        listing: The MaterialListing ORM object (already flushed to the DB
                 but not yet committed — you can mutate it here if needed).

    Returns:
        A non-null risk string that will always be stored on the listing.

    Rules (in priority order):
      1. No invoice  →  HIGHEST RISK, immediately, no further checks.
      2. (Future)    →  Run full scoring algorithm and return RISK_* constant.
    """
    # ── Rule 1: Invoice presence gate ────────────────────────────────────────
    # This rule is unconditional and cannot be overridden by the recycler.
    if listing.invoice_document_id is None:
        return RISK_HIGHEST

    # ── PLUG YOUR ALGORITHM IN HERE ──────────────────────────────────────────
    # The invoice exists.  Run your scoring model and return one of:
    #   RISK_HIGH, RISK_MEDIUM, RISK_LOW
    #
    # Example skeleton:
    #
    #   score = await _call_ml_service(
    #       category=listing.category,
    #       grade=listing.grade,
    #       price_per_unit=listing.price_per_unit,
    #       invoice_doc_id=listing.invoice_document_id,
    #   )
    #   if score < 0.3:
    #       return RISK_LOW
    #   elif score < 0.7:
    #       return RISK_MEDIUM
    #   else:
    #       return RISK_HIGH
    # ─────────────────────────────────────────────────────────────────────────

    # No-op until algorithm is implemented:
    # Return whatever the recycler provided manually, or a neutral default.
    return listing.validity_risk or RISK_MEDIUM
