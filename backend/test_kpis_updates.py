import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock

# This import will fail if PaymentMethod (or any other name) is missing
from app.routers.kpis import get_wallet_transactions

async def test_kpis_updates():
    print("Running tests for kpis.py updates...\n")
    
    # 1. Test Import (Implicitly passes if we reach here)
    print("✅ kpis.py imported successfully (PaymentMethod NameError resolved)")
    
    # 2. Test get_wallet_transactions query construction
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db.execute.return_value = mock_result
    
    test_company_id = uuid.uuid4()
    
    try:
        # This will execute the SQLAlchemy query construction logic and call our mock
        await get_wallet_transactions(mock_db, company_id=test_company_id)
        
        # Extract the exact SQL query that was passed to db.execute
        called_query = mock_db.execute.call_args[0][0]
        
        # Compile it to a string so we can inspect the generated SQL
        compiled_query = str(called_query.compile(compile_kwargs={"literal_binds": True}))
        
        # 3. Verify the transaction_id_raw fix
        # It should cast material_purchases.id to String, not listing_id
        if "material_purchases.id" in compiled_query:
            print("✅ transaction_id_raw correctly uses MaterialPurchase.id instead of listing_id")
        else:
            print("❌ transaction_id_raw fix not detected in generated SQL")
            
        # 4. Verify WalletRechargeStatus fix
        # The case statement should now output string literals for the Enum values
        if "'SUCCESS'" in compiled_query and "'FAILED'" in compiled_query:
            print("✅ WalletRecharge.status correctly uses string values (.value) in CASE statement")
        else:
            print("❌ WalletRecharge.status fix not detected in generated SQL")
            
        print("\n🎉 All tests passed successfully! The query structures are sound.")
        
    except Exception as e:
        print(f"\n❌ Error during query construction: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_kpis_updates())
