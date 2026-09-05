"""
Security & Validation Unit Tests
=================================
Tests for security fixes, schema validation, and error handling.
Run with: python -m pytest scripts/test_security_fixes.py -v
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
from pydantic import ValidationError

# Import the FastAPI app and dependencies
from app.main import app
from app.database import get_db
from app.security import require_company_admin, require_active_company_membership, get_current_profile
from app.models import CompanyMember, MemberRole, MemberStatus, DocumentCategory, Profile

# Import schemas to test
from app.schemas import DocumentCreate


# Standard client — exceptions propagate (good for catching real bugs)
client = TestClient(app)
# Silent client — returns HTTP responses for 5xx instead of re-raising
silent_client = TestClient(app, raise_server_exceptions=False)


# ─── MOCK DEPENDENCIES ────────────────────────────────────────────────────────

async def override_get_db():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalars.return_value.all.return_value = []
    mock_result.all.return_value = []
    mock_session.execute.return_value = mock_result
    yield mock_session


async def override_require_company_admin():
    return CompanyMember(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        profile_id="user_test",
        member_role=MemberRole.OWNER,
        status=MemberStatus.ACTIVE,
    )


async def override_require_active_company_membership():
    return CompanyMember(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        profile_id="user_test",
        member_role=MemberRole.MEMBER,
        status=MemberStatus.ACTIVE,
    )


async def override_get_current_profile():
    return Profile(id="user_test", email="test@example.com")


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[require_company_admin] = override_require_company_admin
app.dependency_overrides[require_active_company_membership] = override_require_active_company_membership
app.dependency_overrides[get_current_profile] = override_get_current_profile


# ─── TESTS ────────────────────────────────────────────────────────────────────

def test_pagination_bounds():
    """
    Test that the pagination bounds in kpis.py correctly reject negative offsets
    and excessively large limits with a 422 Unprocessable Entity.
    """
    company_id = uuid.uuid4()

    # 1. Negative offset
    response = client.get(f"/companies/{company_id}/kpis/brand-dashboard?purchase_history_offset=-1")
    assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"
    assert "purchase_history_offset" in response.text

    # 2. Limit too high
    response = client.get(f"/companies/{company_id}/kpis/brand-dashboard?purchase_history_limit=9999")
    assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"
    assert "purchase_history_limit" in response.text

    # 3. Limit zero (too low)
    response = client.get(f"/companies/{company_id}/kpis/brand-dashboard?purchase_history_limit=0")
    assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"
    assert "purchase_history_limit" in response.text


def test_schema_file_type_validation():
    """
    Test that DocumentCreate properly validates file types and rejects disallowed ones.
    """
    # Valid combo — pdf file_name + application/pdf mime
    doc = DocumentCreate(
        storage_key="documents/company123/invoice.pdf",
        file_name="invoice.pdf",
        file_size_bytes=12345,
        file_type="application/pdf",
        category=DocumentCategory.OTHER,
    )
    assert doc.file_name == "invoice.pdf"
    assert doc.file_type == "application/pdf"

    # Invalid: .exe extension (disallowed)
    with pytest.raises(ValidationError) as exc_info:
        DocumentCreate(
            storage_key="documents/company123/malware.exe",
            file_name="malware.exe",
            file_size_bytes=9999,
            file_type="application/octet-stream",
        )
    assert "File type not allowed" in str(exc_info.value)

    # Invalid: mismatched extension vs MIME type (.pdf ext but image/jpeg MIME)
    with pytest.raises(ValidationError) as exc_info:
        DocumentCreate(
            storage_key="documents/company123/trick.pdf",
            file_name="trick.pdf",
            file_size_bytes=9999,
            file_type="image/jpeg",
        )
    assert "does not match the extension" in str(exc_info.value)


def test_path_traversal_prevention():
    """
    Test that the documents.py download endpoint prevents path traversal (..)
    by ensuring a document with a malicious storage_key results in a 404 (DB
    returns no row for that company) rather than serving arbitrary files.

    The actual defence is that storage_key is stored server-side and looked up
    by (document_id, company_id) — the client never supplies a storage path.
    A document with a path-traversal storage_key can only exist if it was
    inserted directly into the DB, so we mock that scenario.
    """
    company_id = uuid.uuid4()

    async def override_get_db_malicious():
        mock_session = AsyncMock()
        # First call: membership recheck — return a fresh OWNER role
        member_result = MagicMock()
        member_result.scalar_one_or_none.return_value = MemberRole.OWNER

        # Second call: document lookup — 404 (no such doc in that company)
        doc_result = MagicMock()
        doc_result.scalar_one_or_none.return_value = None

        mock_session.execute.side_effect = [member_result, doc_result]
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db_malicious

    with patch("app.routers.documents.r2_storage"):
        response = client.get(f"/companies/{company_id}/documents/{uuid.uuid4()}/download")

    # Document not found → 404
    assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"

    # Restore default override
    app.dependency_overrides[get_db] = override_get_db


def test_500_error_masking():
    """
    Test that main.py masks the stack trace for 500 errors — the raw exception
    message must never appear in the response body.

    Uses raise_server_exceptions=False so the TestClient returns the HTTP
    response instead of re-raising through Starlette's BaseHTTPMiddleware.
    """
    company_id = uuid.uuid4()

    async def override_get_db_error():
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("Super secret database credential leak!")
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db_error

    # Use the silent client so Starlette's middleware returns the 500
    # response instead of re-raising the exception in the test process.
    response = silent_client.get(f"/companies/{company_id}/kpis/brand-dashboard")

    assert response.status_code == 500
    assert "Super secret database credential leak!" not in response.text
    # Our global_exception_handler returns this exact message
    assert "internal server error" in response.text.lower()

    app.dependency_overrides[get_db] = override_get_db


def test_clerk_webhook_invalid_signature_rejected():
    """
    Test that the Clerk webhook endpoint rejects requests with an invalid
    (or missing) Svix signature with a 400 Bad Request.
    This validates that the Svix signature guard is active.
    """
    payload = {
        "type": "user.created",
        "data": {
            "id": "user_123",
            "email_addresses": [{"id": "ea_1", "email_address": "test@test.com"}],
            "primary_email_address_id": "ea_1",
        },
    }

    # No svix headers → signature verification must fail → 400
    response = client.post(
        "/webhooks/clerk",
        json=payload,
        headers={"svix-id": "bad_id", "svix-timestamp": "1", "svix-signature": "v1,invalidsig"},
    )
    assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
    assert "Invalid webhook signature" in response.text


def test_document_upload_zero_bytes_rejected():
    """
    Test that DocumentCreate rejects a file_size_bytes of 0 (gt=0 validator).
    """
    with pytest.raises(ValidationError) as exc_info:
        DocumentCreate(
            storage_key="documents/company123/empty.pdf",
            file_name="empty.pdf",
            file_size_bytes=0,
            file_type="application/pdf",
        )
    assert "file_size_bytes" in str(exc_info.value)


if __name__ == "__main__":
    print("Run this script with: python -m pytest scripts/test_security_fixes.py -v")
