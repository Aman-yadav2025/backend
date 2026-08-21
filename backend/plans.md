# Project Master Plan

This document serves as the living roadmap for the ongoing development of the backend platform. We will build out this plan iteratively as new requirements are clarified.

---

## Phase 1: Comprehensive Backend Security Testing
*Status: Pending*

Before we expand the feature set, we must execute the tests outlined in `TEST.md` to ensure the core authentication, RBAC, webhooks, and concurrency locks are completely bulletproof.

**Tasks:**
- [ ] Set up `pytest` and `httpx` for asynchronous API testing.
- [ ] Write integration tests for RBAC boundaries (Admin vs Brand Admin vs Recycler).
- [ ] Write webhook simulation tests (Clerk & Razorpay signature validation).
- [ ] Test the background deletion worker and soft delete edge cases.

---

## Phase 2: Brand Dashboard & KPIs
*Status: Planning*

We will build the data aggregation endpoints for the Brand Dashboard.

**Open Questions:**
1. **Target Metrics:** What exactly are the KPIs? (e.g., "Total kg of Plastic Recycled", "Total CO2 Offset", "Pending Compliance Documents", "Money Spent").
2. **Time Series:** Do the KPIs need to show historical trends (e.g., "Recycling by Month" line charts), or just lifetime totals?

---

## Phase 3: Recycler Dashboard & Invoice/Contract Upload
*Status: Planning*

Following the Brand KPIs, we will implement the Recycler Dashboard and the core contract upload workflow.

**Workflow:**
1. **Contract/Invoice Upload:** Recyclers upload their invoices/contracts to the platform.
2. **Algorithmic Verification:** The backend runs the invoice through a custom verification algorithm (to be defined).
3. **Risk Scoring:** Based on the algorithm's output, the contract is automatically assigned a risk status:
   - `SAFE`
   - `RISKY`
   - `DANGER`

---

## Phase 4: Recycling Contract Marketplace
*Status: Planning*

Once a Recycler's contract is verified and scored, it becomes available on a public marketplace for Brands to purchase.

**Workflow:**
1. **Listing:** Recyclers list their verified contracts on the marketplace and set their own prices.
2. **Purchasing (Brand ➔ Recycler):** Brands browse the marketplace and purchase contracts to meet their recycling targets.
3. **Metric Assignment:** Upon successful purchase, the contract's specific metrics (e.g., recycled volume) and the paid amount are credited to the purchasing Brand's company profile and dashboard KPIs.

**Open Questions:**
1. **Platform Fee:** Do we charge a platform fee (commission) on these marketplace transactions between the Brand and the Recycler?
2. **Marketplace UI/Filtering:** How will brands filter contracts? (e.g., by plastic type, risk status, location, or price per kg?)

---

## Phase 5: Direct Brand Invoice Processing
*Status: Planning*

Brands are not forced to buy contracts from our marketplace; they can also bring their own off-platform recyclers.

**Workflow:**
1. **Direct Upload:** Brands can directly upload invoices from their own external recyclers.
2. **Verification & Metric Assignment:** The platform will process and verify these invoices and update the Brand's dashboard metrics (volume recycled, etc.).
3. **No Financial Routing:** No payments will be processed through the platform for these direct uploads, as the financial transaction happened off-platform.
