import asyncio
import argparse
import sys
from pathlib import Path
from typing import Set

# Add the 'backend' directory to sys.path so 'app' module can be imported
sys.path.append(str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import Document
from app.config import settings
from app.services.r2_storage import _s3_client

async def get_all_db_storage_keys() -> Set[str]:
    """Fetch all known document storage keys from the database."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Document.storage_key))
        return {row[0] for row in result.all()}

def get_all_bucket_keys() -> Set[str]:
    """Fetch all object keys currently residing in the configured R2 bucket."""
    bucket_keys = set()
    paginator = _s3_client.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=settings.r2_bucket_name)

    for page in pages:
        if "Contents" in page:
            for obj in page["Contents"]:
                bucket_keys.add(obj["Key"])
                
    return bucket_keys

def chunked_iterable(iterable, size):
    """Yield successive chunks of a given size from an iterable."""
    iterator = iter(iterable)
    chunk = []
    for item in iterator:
        chunk.append(item)
        if len(chunk) == size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk

async def main(dry_run: bool):
    print("🧹 Starting R2 Bucket Cleanup Script...")
    
    # 1. Fetch source of truth (DB)
    print("Fetching active storage keys from the database...")
    db_keys = await get_all_db_storage_keys()
    print(f"-> Found {len(db_keys)} valid documents in the database.")

    # 2. Fetch current state of the bucket.
    # get_all_bucket_keys() is a synchronous blocking call (boto3 pagination).
    # Run it in a thread so it doesn't block the asyncio event loop.
    print(f"Fetching objects from R2 bucket: {settings.r2_bucket_name}...")
    bucket_keys = await asyncio.to_thread(get_all_bucket_keys)
    print(f"-> Found {len(bucket_keys)} objects in the bucket.")

    # 3. Compute orphans
    orphans = bucket_keys - db_keys
    print(f"\nAnalysis complete. Found {len(orphans)} orphaned files in the bucket.")

    if not orphans:
        print("Nothing to clean up! Exiting.")
        return

    if dry_run:
        print("\n[DRY RUN] The following files WOULD be deleted:")
        for k in orphans:
            print(f" - {k}")
        print("\nRun with --confirm to actually delete these files.")
        return

    # 4. Perform the deletion (chunked by 1000 per S3 bulk delete limits)
    print("\nStarting deletion of orphaned files...")
    total_deleted = 0
    
    for chunk in chunked_iterable(orphans, 1000):
        objects_to_delete = [{'Key': key} for key in chunk]
        response = await asyncio.to_thread(
            _s3_client.delete_objects,
            Bucket=settings.r2_bucket_name,
            Delete={'Objects': objects_to_delete, 'Quiet': True}
        )
        
        # 'Errors' key will be present if any specific objects failed to delete
        if 'Errors' in response:
            print(f"⚠️ Encountered errors while deleting a batch:")
            for err in response['Errors']:
                print(f"   - {err['Key']}: {err['Code']} ({err['Message']})")
            
            success_count = len(chunk) - len(response['Errors'])
            total_deleted += success_count
        else:
            total_deleted += len(chunk)
            
    print(f"\n✅ Cleanup complete. Deleted {total_deleted} files.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Clean orphaned documents from R2 storage.",
        epilog="Defaults to dry-run mode. Pass --confirm to actually delete files.",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually delete orphaned files. Without this flag the script only prints what it would delete.",
    )
    args = parser.parse_args()

    # Default to dry-run unless explicitly confirmed to prevent accidental deletions.
    asyncio.run(main(dry_run=not args.confirm))
