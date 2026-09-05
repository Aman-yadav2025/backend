"""
Brand KPIs – Wallet Transactions Query Unit Tests
==================================================
Verifies the SQL query structure produced by get_wallet_transactions.
Run with: python -m pytest test_kpis_updates.py -v
"""
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock

from app.routers.kpis import get_wallet_transactions


@pytest.mark.anyio
async def test_wallet_transactions_uses_purchase_id():
    """
    Verifies that the UNION ALL query uses MaterialPurchase.id (not listing_id)
    as the transaction_id_raw column for debit rows.
    """
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db.execute.return_value = mock_result

    company_id = uuid.uuid4()
    await get_wallet_transactions(mock_db, company_id=company_id)

    called_query = mock_db.execute.call_args[0][0]
    compiled = str(called_query.compile(compile_kwargs={"literal_binds": True}))

    assert "material_purchases.id" in compiled, (
        "Expected material_purchases.id used as transaction_id_raw, got:\n" + compiled
    )


@pytest.mark.anyio
async def test_wallet_transactions_recharge_status_uses_string_values():
    """
    Verifies that WalletRecharge.status CASE statement uses .value string
    literals ('SUCCESS', 'FAILED') rather than Enum member names.
    """
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db.execute.return_value = mock_result

    company_id = uuid.uuid4()
    await get_wallet_transactions(mock_db, company_id=company_id)

    called_query = mock_db.execute.call_args[0][0]
    compiled = str(called_query.compile(compile_kwargs={"literal_binds": True}))

    assert "'SUCCESS'" in compiled, "Expected 'SUCCESS' string literal in CASE statement"
    assert "'FAILED'" in compiled, "Expected 'FAILED' string literal in CASE statement"
