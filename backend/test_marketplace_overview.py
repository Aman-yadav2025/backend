"""
Marketplace Overview – Query Unit Test
=======================================
Verifies that get_marketplace_overview executes without error and produces
a valid SQL query.
Run with: python -m pytest test_marketplace_overview.py -v
"""
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from app.routers.marketplace_overview import get_marketplace_overview


@pytest.mark.anyio
async def test_marketplace_overview_query_executes():
    """
    Calls get_marketplace_overview with a mocked DB session and verifies
    the generated SQL is well-formed (compiles without error).
    """
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_row = MagicMock()
    mock_row.total_volume = Decimal("100.50")
    mock_row.total_listings = 5
    mock_row.avg_plastic = Decimal("12.0")
    mock_row.avg_metal = Decimal("0.00")
    mock_row.total_recyclers = 3
    mock_result.one.return_value = mock_row
    mock_db.execute.return_value = mock_result

    result = await get_marketplace_overview(db=mock_db)

    assert mock_db.execute.called, "Expected db.execute to be called"

    called_query = mock_db.execute.call_args[0][0]
    compiled = str(called_query.compile(compile_kwargs={"literal_binds": True}))

    # Verify the query references the listings table
    assert "material_listings" in compiled, (
        "Expected 'material_listings' in compiled SQL"
    )
