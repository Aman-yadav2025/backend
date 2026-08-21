import asyncio
import uuid

import boto3
from botocore.config import Config

from app.config import settings

_s3_client = boto3.client(
    "s3",
    endpoint_url=settings.r2_endpoint_url,
    aws_access_key_id=settings.r2_access_key_id,
    aws_secret_access_key=settings.r2_secret_access_key.get_secret_value(),
    # path-style addressing (http://host/bucket/key instead of
    # http://bucket.host/key) works against both Cloudflare R2 and
    # MinIO/other local S3-compatible servers used for dev testing,
    # so this doesn't need to change when you swap R2_ENDPOINT_URL later.
    config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    region_name="auto",
)


def build_storage_key(company_id: uuid.UUID, category: str, file_name: str) -> str:
    """Namespace every object under the owning company so a leaked key still
    reveals nothing cross-tenant, and dedupe collisions with a random prefix.
    """
    unique = uuid.uuid4().hex
    safe_name = file_name.replace("/", "_").replace("\\", "_")
    return f"companies/{company_id}/{category.lower()}/{unique}_{safe_name}"


def generate_presigned_upload_url(storage_key: str, content_type: str) -> str:
    return _s3_client.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": settings.r2_bucket_name,
            "Key": storage_key,
            "ContentType": content_type,
        },
        ExpiresIn=settings.r2_presigned_url_expiry_seconds,
    )


def generate_presigned_download_url(storage_key: str) -> str:
    return _s3_client.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": settings.r2_bucket_name, "Key": storage_key},
        ExpiresIn=settings.r2_presigned_url_expiry_seconds,
    )


async def delete_object(storage_key: str) -> None:
    await asyncio.to_thread(_s3_client.delete_object, Bucket=settings.r2_bucket_name, Key=storage_key)
