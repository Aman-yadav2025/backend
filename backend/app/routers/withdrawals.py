"""
Withdrawals router
==================
Allows Recyclers to save bank/UPI details and request wallet withdrawals.
Admins manually pay the recycler and then log the approval with a
transaction reference (UTR / UPI ref).

Wallet math:
  POST /withdrawals    → frozen_wallet_balance += amount
  Admin APPROVED       → frozen_wallet_balance -= amount, wallet_balance -= amount (admin.py)
  Admin REJECTED       → frozen_wallet_balance -= amount (admin.py)

Endpoint summary:
  POST   /companies/{company_id}/bank-accounts          — Add bank/UPI account
  GET    /companies/{company_id}/bank-accounts          — List bank/UPI accounts
  DELETE /companies/{company_id}/bank-accounts/{id}     — Remove a bank/UPI account
  POST   /companies/{company_id}/withdrawals            — Request a withdrawal
  GET    /companies/{company_id}/withdrawals            — List withdrawal history
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import (
    BankAccount,
    Company,
    CompanyMember,
    CompanyType,
    WithdrawalRequest,
    WithdrawalStatus,
)
from app.schemas import (
    BankAccountCreate,
    BankAccountOut,
    WithdrawalRequestCreate,
    WithdrawalRequestOut,
)
from app.security import require_company_admin

router = APIRouter(
    prefix="/companies/{company_id}",
    tags=["withdrawals"],
)


# ── Helper: verify the company is a RECYCLER and the caller is an admin ───────

async def _require_recycler_admin(
    company_id: uuid.UUID,
    admin_member: CompanyMember = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
) -> Company:
    company = await db.scalar(
        select(Company).where(
            Company.id == company_id,
            Company.deleted_at.is_(None),
        )
    )
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    if company.company_type != CompanyType.RECYCLER:
        raise HTTPException(status_code=403, detail="Only Recycler companies can manage withdrawals")
    return company


# ── Bank Accounts ─────────────────────────────────────────────────────────────

@router.post("/bank-accounts", response_model=BankAccountOut, status_code=status.HTTP_201_CREATED)
async def add_bank_account(
    company_id: uuid.UUID,
    body: BankAccountCreate,
    company: Company = Depends(_require_recycler_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Save a bank account or UPI ID for this Recycler.
    Provide either (beneficiary_name + account_number + ifsc_code) for bank transfer,
    or upi_id for UPI transfer.
    """
    account = BankAccount(
        company_id=company_id,
        beneficiary_name=body.beneficiary_name,
        account_number=body.account_number,
        ifsc_code=body.ifsc_code,
        upi_id=body.upi_id,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


@router.get("/bank-accounts", response_model=list[BankAccountOut])
async def list_bank_accounts(
    company_id: uuid.UUID,
    company: Company = Depends(_require_recycler_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all saved bank accounts / UPI IDs for this Recycler."""
    result = await db.execute(
        select(BankAccount)
        .where(
            BankAccount.company_id == company_id,
            BankAccount.deleted_at.is_(None),
        )
        .order_by(BankAccount.created_at.desc())
    )
    return result.scalars().all()


@router.delete("/bank-accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bank_account(
    company_id: uuid.UUID,
    account_id: uuid.UUID,
    company: Company = Depends(_require_recycler_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Remove a saved bank/UPI account.
    Not allowed if the account has any PENDING withdrawal requests.
    """
    # Lock the account row first — prevents a concurrent request_withdrawal
    # from slipping a withdrawal in between our pending-check and the delete.
    account = await db.scalar(
        select(BankAccount).where(
            BankAccount.id == account_id,
            BankAccount.company_id == company_id,
            BankAccount.deleted_at.is_(None),
        ).with_for_update()
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Bank account not found")

    # Block deletion if there's a pending withdrawal tied to this account.
    # Read is done inside the same transaction that holds the account lock,
    # so no withdrawal can be created after this check completes.
    pending = await db.scalar(
        select(WithdrawalRequest.id).where(
            WithdrawalRequest.bank_account_id == account_id,
            WithdrawalRequest.status == WithdrawalStatus.PENDING,
        )
    )
    if pending is not None:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete this account while it has a pending withdrawal request.",
        )

    # Soft-delete the account so existing withdrawal requests aren't orphaned
    account.deleted_at = func.now()
    await db.commit()


# ── Withdrawal Requests ───────────────────────────────────────────────────────

@router.post("/withdrawals", response_model=WithdrawalRequestOut, status_code=status.HTTP_201_CREATED)
async def request_withdrawal(
    company_id: uuid.UUID,
    body: WithdrawalRequestCreate,
    company: Company = Depends(_require_recycler_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Request a wallet withdrawal.

    Immediately increases frozen_wallet_balance by the requested amount
    so it cannot be double-spent on the marketplace while the admin review is pending.
    (Note: wallet_balance includes frozen funds, so available = wallet - frozen).
    """
    # ── 1. Lock the company row (force fresh read via refresh) ───────────────
    # The _require_recycler_admin dependency already fetched this Company into
    # the session identity map. A plain select().with_for_update() acquires the
    # DB lock but SQLAlchemy would return the cached Python object with stale
    # wallet_balance / frozen_wallet_balance values.
    # db.refresh(..., with_for_update=True) acquires the lock AND re-reads all
    # columns from the DB into the existing object — same pattern as confirm_delivery.
    await db.refresh(company, with_for_update=True)
    if company.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Company not found")

    # ── 2. Verify bank account belongs to this company (locked) ──────────────
    # Lock the bank account row so a concurrent DELETE cannot remove it
    # between this check and the commit that creates the WithdrawalRequest.
    account = await db.scalar(
        select(BankAccount).where(
            BankAccount.id == body.bank_account_id,
            BankAccount.company_id == company_id,
            BankAccount.deleted_at.is_(None),
        ).with_for_update()
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Bank account not found")

    # ── 3. Validate available balance ─────────────────────────────────────────
    # available = wallet_balance - frozen_wallet_balance
    # (frozen already contains money ring-fenced for other pending withdrawals/purchases)
    available = company.wallet_balance - company.frozen_wallet_balance
    if body.amount > available:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Insufficient available balance. "
                f"Available: ₹{available:.2f}, Requested: ₹{body.amount:.2f}."
            ),
        )

    # ── 4. Freeze the amount ──────────────────────────────────────────────────
    company.frozen_wallet_balance += body.amount

    # ── 5. Create the withdrawal request ─────────────────────────────────────
    withdrawal = WithdrawalRequest(
        company_id=company_id,
        bank_account_id=body.bank_account_id,
        amount=body.amount,
        status=WithdrawalStatus.PENDING,
    )
    db.add(withdrawal)

    await db.commit()
    await db.refresh(withdrawal)
    return withdrawal


@router.get("/withdrawals", response_model=list[WithdrawalRequestOut])
async def list_withdrawals(
    company_id: uuid.UUID,
    _company: Company = Depends(_require_recycler_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all withdrawal requests for this Recycler, newest first."""
    result = await db.execute(
        select(WithdrawalRequest)
        .where(WithdrawalRequest.company_id == company_id)
        .order_by(WithdrawalRequest.created_at.desc())
    )
    return result.scalars().all()
