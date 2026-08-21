## 6. Platform Admin Operations

Admin endpoints have the highest privilege and must be guarded against race conditions and data corruption.

- [x] **Document Verification Constraints:** Attempt to verify a document but pass `status = PENDING_VERIFICATION`. *Expected: 422 Validation Error (Literal typing restricts to VERIFIED/REJECTED).*
- [x] **Concurrent Refund Approvals (Critical Race):** Have two admins approve two different refund requests for the *same* payment simultaneously. *Expected: Payment row lock ensures total approved is calculated sequentially, preventing total refunds from exceeding the paid amount.*
- [x] **Refund-Before-Call Validation:** Approve a refund request that exceeds the allowed amount. *Expected: Backend halts and returns 400 *before* calling the Razorpay API, preventing orphaned money movement.*
- [x] **Audit Trail Enforcement:** Verify a document and approve a refund. *Expected: The DB accurately records the admin's profile ID in `verified_by`/`actioned_by` and the exact timestamp.*
- [x] **Safe Payment Status Reset:** Reject all pending refunds on a payment that previously had one successful partial refund. *Expected: The payment status correctly reverts to `PARTIALLY_REFUNDED` (not `SUCCESS`) based on the `SUM` of approved refunds.*
