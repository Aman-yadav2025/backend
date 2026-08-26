import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import CompanyMember, Document, Profile, MemberRole, MemberStatus, DocumentStatus
from app.rate_limit import limiter
from app.schemas import (
    DocumentCreate,
    DocumentDownloadResponse,
    DocumentOut,
    DocumentPresignRequest,
    DocumentPresignResponse,
)
from app.security import get_current_profile, require_active_company_membership, require_company_admin
from app.services import r2_storage

router = APIRouter(prefix="/companies/{company_id}/documents", tags=["documents"])


@router.post("/presign", response_model=DocumentPresignResponse)
@limiter.limit("10/minute")  # Strict: prevents R2 presigned URL exhaustion attacks
async def presign_upload(
    request: Request,  # Required by SlowAPI to extract the client IP
    company_id: uuid.UUID,
    body: DocumentPresignRequest,
    _membership: CompanyMember = Depends(require_active_company_membership),
):
    if body.file_size_bytes > settings.r2_max_upload_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds max allowed size of {settings.r2_max_upload_bytes} bytes",
        )


    storage_key = r2_storage.build_storage_key(company_id, body.category.value, body.file_name)
    upload_url = r2_storage.generate_presigned_upload_url(storage_key, body.file_type)

    return DocumentPresignResponse(
        upload_url=upload_url,
        storage_key=storage_key,
        expires_in_seconds=settings.r2_presigned_url_expiry_seconds,
    )


@router.post("", response_model=DocumentOut, status_code=201)
async def create_document_record(
    company_id: uuid.UUID,
    body: DocumentCreate,
    membership: CompanyMember = Depends(require_active_company_membership),
    profile: Profile = Depends(get_current_profile),
    db: AsyncSession = Depends(get_db),
):
    """Call this AFTER the client has successfully PUT the file to the
    presigned upload_url — this writes the pointer row described in the
    README's document-storage flow.
    """
    if not body.storage_key.startswith(f"companies/{company_id}/"):
        raise HTTPException(status_code=400, detail="storage_key does not belong to this company")

    if body.file_size_bytes > settings.r2_max_upload_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds max allowed size of {settings.r2_max_upload_bytes} bytes",
        )

    if membership.id is not None:
        recheck = await db.execute(
            select(CompanyMember).where(
                CompanyMember.id == membership.id,
                CompanyMember.status == MemberStatus.ACTIVE
            ).with_for_update()
        )
        if not recheck.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Membership revoked during request")

    document = Document(
        company_id=company_id,
        uploaded_by_profile_id=profile.id,
        file_name=body.file_name,
        storage_key=body.storage_key,
        file_size_bytes=body.file_size_bytes,
        file_type=body.file_type,
        category=body.category,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    return document


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    company_id: uuid.UUID,
    _membership: CompanyMember = Depends(require_active_company_membership),
    profile: Profile = Depends(get_current_profile),
    db: AsyncSession = Depends(get_db),
):
    member_role = _membership.member_role
    if _membership.id is not None:
        member_res = await db.execute(
            select(CompanyMember.member_role).where(
                CompanyMember.id == _membership.id,
                CompanyMember.status == MemberStatus.ACTIVE
            )
        )
        fresh_role = member_res.scalar_one_or_none()
        if fresh_role is None:
            raise HTTPException(status_code=403, detail="Membership revoked")
        member_role = fresh_role

    query = select(Document).where(Document.company_id == company_id)
    if member_role != MemberRole.OWNER:
        query = query.where(Document.uploaded_by_profile_id == profile.id)
        
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{document_id}/download", response_model=DocumentDownloadResponse)
async def get_download_url(
    company_id: uuid.UUID,
    document_id: uuid.UUID,
    _membership: CompanyMember = Depends(require_active_company_membership),
    profile: Profile = Depends(get_current_profile),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.company_id == company_id)
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
        
    member_role = _membership.member_role
    if _membership.id is not None:
        member_res = await db.execute(
            select(CompanyMember.member_role).where(
                CompanyMember.id == _membership.id,
                CompanyMember.status == MemberStatus.ACTIVE
            )
        )
        fresh_role = member_res.scalar_one_or_none()
        if fresh_role is None:
            raise HTTPException(status_code=403, detail="Membership revoked")
        member_role = fresh_role
        
    if member_role != MemberRole.OWNER and document.uploaded_by_profile_id != profile.id:
        raise HTTPException(status_code=403, detail="Not authorized to download this document")

    url = r2_storage.generate_presigned_download_url(document.storage_key)
    return DocumentDownloadResponse(download_url=url, expires_in_seconds=settings.r2_presigned_url_expiry_seconds)


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    company_id: uuid.UUID,
    document_id: uuid.UUID,
    _admin_membership: CompanyMember = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.company_id == company_id).with_for_update()
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    if _admin_membership.id is not None:
        recheck = await db.execute(
            select(CompanyMember).where(
                CompanyMember.id == _admin_membership.id,
                CompanyMember.status == MemberStatus.ACTIVE,
                CompanyMember.member_role == MemberRole.OWNER
            ).with_for_update()
        )
        if not recheck.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Admin privileges revoked during request")

    # CRITICAL: Delete from DB first, then R2. 
    # If R2 deletion fails, we leak an orphaned object in R2 (cheap, harmless).
    # If DB commit fails after R2 deletion, we leave a DB record pointing to a non-existent file (fatal).
    storage_key = document.storage_key
    await db.delete(document)
    await db.commit()

    try:
        await r2_storage.delete_object(storage_key)
    except Exception as e:
        logging.error(f"Failed to delete document {storage_key} from R2: {e}")


# NOTE: VERIFIED/REJECTED status transitions are intentionally NOT exposed
# here — per your answer, that workflow isn't defined yet. Add a
# PATCH /{document_id}/status endpoint (with the appropriate role check)
# once the verification flow is specified.

@router.put("/{document_id}", response_model=DocumentOut)
async def reupload_document(
    company_id: uuid.UUID,
    document_id: uuid.UUID,
    body: DocumentCreate,
    _membership: CompanyMember = Depends(require_active_company_membership),
    profile: Profile = Depends(get_current_profile),
    db: AsyncSession = Depends(get_db),
):
    """
    Called after the client successfully PUTs a new file to a presigned URL.
    Updates the existing document record to point to the new file and resets
    its status to PENDING_VERIFICATION.
    """
    if not body.storage_key.startswith(f"companies/{company_id}/"):
        raise HTTPException(status_code=400, detail="storage_key does not belong to this company")

    if body.file_size_bytes > settings.r2_max_upload_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds max allowed size of {settings.r2_max_upload_bytes} bytes",
        )

    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.company_id == company_id).with_for_update()
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    member_role = _membership.member_role
    if _membership.id is not None:
        recheck = await db.execute(
            select(CompanyMember).where(
                CompanyMember.id == _membership.id,
                CompanyMember.status == MemberStatus.ACTIVE
            ).with_for_update()
        )
        current_member = recheck.scalar_one_or_none()
        if not current_member:
            raise HTTPException(status_code=403, detail="Membership revoked during request")
        member_role = current_member.member_role
            
    if member_role != MemberRole.OWNER and document.uploaded_by_profile_id != profile.id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this document")

    # Optionally, we could delete the old object from R2 here to save space
    # await r2_storage.delete_object(document.storage_key)

    document.uploaded_by_profile_id = profile.id
    document.file_name = body.file_name
    document.storage_key = body.storage_key
    document.file_size_bytes = body.file_size_bytes
    document.file_type = body.file_type
    document.category = body.category
    document.status = DocumentStatus.PENDING_VERIFICATION
    document.rejection_reason = None

    await db.commit()
    await db.refresh(document)
    return document
