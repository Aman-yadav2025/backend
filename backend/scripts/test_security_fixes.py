import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
from pydantic import ValidationError
from httpx import AsyncClient

# Import the FastAPI app and dependencies
from app.main import app
from app.database import get_db
from app.security import require_company_admin, require_company_member
from app.models import CompanyMember, MemberRole, MemberStatus, CompanyType

# Import schemas to test
from app.schemas import DocumentCreate, InvoiceProofCreate

# Create a test client
client = TestClient(app)

# ─── MOCK DEPENDENCIES ────────────────────────────────────────────────────────

async def override_get_db():
    mock_session = AsyncMock()
    # Mock for standard execute().scalar_one_or_none()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalars.return_value.all.return_value = []
    mock_result.all.return_value = []
    mock_session.execute.return_value = mock_result
    
    # Simulate DB raising an exception to test 500 error masking
    async def mock_execute_raise(*args, **kwargs):
        raise Exception("Database connection lost deeply nested error")
    
    mock_session.execute_raise = mock_execute_raise
    yield mock_session

async def override_require_company_admin():
    return CompanyMember(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        profile_id=uuid.uuid4(),
        role=MemberRole.ADMIN,
        status=MemberStatus.ACTIVE
    )

async def override_require_company_member():
    return CompanyMember(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        profile_id=uuid.uuid4(),
        role=MemberRole.MEMBER,
        status=MemberStatus.ACTIVE
    )

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[require_company_admin] = override_require_company_admin
app.dependency_overrides[require_company_member] = override_require_company_member


# ─── TESTS ────────────────────────────────────────────────────────────────────

def test_pagination_bounds():
    """
    Test that the pagination bounds in kpis.py correctly reject negative offsets
    and excessively large limits with a 422 Unprocessable Entity.
    """
    company_id = uuid.uuid4()
    
    # 1. Negative offset
    response = client.get(f"/companies/{company_id}/kpis/brand-dashboard?purchase_history_offset=-1")
    assert response.status_code == 422
    assert "purchase_history_offset" in response.text
    assert "greater than or equal to 0" in response.text

    # 2. Limit too high
    response = client.get(f"/companies/{company_id}/kpis/brand-dashboard?purchase_history_limit=9999")
    assert response.status_code == 422
    assert "purchase_history_limit" in response.text
    assert "less than or equal to 100" in response.text
    
    # 3. Limit zero (too low)
    response = client.get(f"/companies/{company_id}/kpis/brand-dashboard?purchase_history_limit=0")
    assert response.status_code == 422
    assert "purchase_history_limit" in response.text
    assert "greater than 0" in response.text


def test_schema_mime_type_validation():
    """
    Test that schemas.py properly cross-validates MIME types and file extensions.
    """
    # Valid combo
    doc = DocumentCreate(
        document_name="Invoice",
        category="INVOICE",
        file_extension=".pdf",
        mime_type="application/pdf"
    )
    assert doc.file_extension == ".pdf"
    
    # Invalid combo
    with pytest.raises(ValidationError) as exc_info:
        DocumentCreate(
            document_name="Invoice",
            category="INVOICE",
            file_extension=".jpg",
            mime_type="application/pdf"
        )
    assert "MIME type application/pdf does not match file extension .jpg" in str(exc_info.value)


def test_path_traversal_prevention():
    """
    Test that the documents.py download endpoint prevents path traversal (..)
    """
    company_id = uuid.uuid4()
    
    # We can't easily test the exact DB TOCTOU here without complex mocks,
    # but we CAN test that the endpoint would 422 or 404/403 if it gets weird input.
    # The actual path traversal fix was inside the storage_key check. Let's mock a document 
    # with a bad storage_key.
    
    with patch("app.routers.documents.boto3.client"):
        # We override get_db locally for this test to return a document with a malicious storage_key
        async def override_get_db_malicious():
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_doc = MagicMock()
            mock_doc.company_id = company_id
            mock_doc.storage_key = "../../etc/passwd"
            
            mock_result.scalar_one_or_none.return_value = mock_doc
            mock_session.execute.return_value = mock_result
            yield mock_session
            
        app.dependency_overrides[get_db] = override_get_db_malicious
        
        response = client.get(f"/companies/{company_id}/documents/{uuid.uuid4()}/download")
        
        # It should raise 400 Bad Request because of path traversal
        assert response.status_code == 400
        assert "Invalid document path" in response.text
        
        # Restore default override
        app.dependency_overrides[get_db] = override_get_db


def test_500_error_masking():
    """
    Test that main.py masks the stack trace for 500 errors.
    """
    # We will trigger a route we know exists, but force the DB to raise an error
    company_id = uuid.uuid4()
    
    async def override_get_db_error():
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("Super secret database credential leak!")
        yield mock_session
        
    app.dependency_overrides[get_db] = override_get_db_error
    
    response = client.get(f"/companies/{company_id}/kpis")
    
    assert response.status_code == 500
    assert "Super secret database credential leak!" not in response.text
    assert response.json() == {"detail": "Internal Server Error"}
    
    app.dependency_overrides[get_db] = override_get_db


def test_clerk_webhook_error_handling():
    """
    Test that clerk_webhooks.py returns 500 (not 200) when an error occurs.
    """
    # The webhook signature verification will fail since we don't have a valid signature
    # But let's mock it to pass, then fail on DB.
    
    with patch("app.routers.clerk_webhooks.verify_clerk_signature", return_value=True):
        async def override_get_db_error():
            mock_session = AsyncMock()
            mock_session.execute.side_effect = Exception("DB Error")
            yield mock_session
            
        app.dependency_overrides[get_db] = override_get_db_error
        
        payload = {
            "type": "user.created",
            "data": {"id": "user_123", "email_addresses": [{"email_address": "test@test.com"}]}
        }
        
        response = client.post("/webhooks/clerk", json=payload, headers={"svix-id": "1", "svix-timestamp": "1", "svix-signature": "1"})
        
        # Should be 500 because of the DB error, not 200 (which would swallow the failure)
        assert response.status_code == 500
        
        app.dependency_overrides[get_db] = override_get_db


def test_collector_purchase_ownership():
    """
    Test that updating a collector purchase validates ownership (admin or creator).
    We test the 403 Forbidden case (non-admin, non-creator).
    """
    company_id = uuid.uuid4()
    purchase_id = uuid.uuid4()
    
    # Member making request is NOT an admin
    async def override_require_member():
        return CompanyMember(
            id=uuid.uuid4(), # Different ID from creator
            company_id=company_id,
            profile_id=uuid.uuid4(),
            role=MemberRole.MEMBER, # Standard member
            status=MemberStatus.ACTIVE
        )
        
    async def override_get_db_purchase():
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_purchase = MagicMock()
        mock_purchase.recycler_id = company_id
        mock_purchase.created_by_profile_id = uuid.uuid4() # Someone else created it
        
        # Ensure the DB check passes but ownership check fails
        mock_result.scalar_one_or_none.return_value = mock_purchase
        
        # We also need to mock the membership recheck
        mock_member_recheck = MagicMock()
        mock_member_recheck.status = MemberStatus.ACTIVE
        
        mock_session.execute.side_effect = [
            mock_result, # First call: get purchase
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_member_recheck)) # Second call: membership recheck
        ]
        
        yield mock_session
        
    app.dependency_overrides[require_company_admin] = override_require_member # Use require_company_member equivalent for this endpoint since it's open to members
    # Actually, the endpoint uses require_company_member, so we override that
    app.dependency_overrides[require_company_member] = override_require_member
    app.dependency_overrides[get_db] = override_get_db_purchase
    
    payload = {
        "material_type": "PET",
        "quantity": 100.0,
        "price_per_unit": 50.0
    }
    
    response = client.put(f"/companies/{company_id}/collector-purchases/{purchase_id}", json=payload)
    
    # Should be 403 Forbidden because they are not an admin and didn't create it
    assert response.status_code == 403
    assert "Not authorized to modify this purchase" in response.text
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_company_member] = override_require_company_member


if __name__ == "__main__":
    print("Run this script with: pytest scripts/test_security_fixes.py -v")
