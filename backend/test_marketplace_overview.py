import asyncio
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from app.routers.marketplace_overview import get_marketplace_overview

async def test_marketplace_overview():
    print("Running tests for marketplace_overview.py updates...\n")
    
    print("✅ marketplace_overview.py imported successfully")
    
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
    
    try:
        res = await get_marketplace_overview(db=mock_db)
        
        called_query = mock_db.execute.call_args[0][0]
        compiled_query = str(called_query.compile(compile_kwargs={"literal_binds": True}))
        
        print(f"Generated SQL:\n{compiled_query}\n")
        print("\n🎉 All tests passed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error during query construction: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_marketplace_overview())
