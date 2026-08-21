"""
Standalone R2 connectivity test — run this directly after filling in the
R2_* values in .env, BEFORE testing through the FastAPI endpoints (which
require a Clerk JWT you don't have yet).

Usage (from the backend/ folder, with your venv active):
    python scripts/test_r2_connection.py

It generates a presigned upload URL, uploads a small test file to it,
generates a presigned download URL, downloads it back, and confirms the
bytes match. Prints PASS/FAIL for each step.
"""

import asyncio
import sys
import uuid

import requests

sys.path.insert(0, ".")  # allow running from backend/ without installing the package

from app.services import r2_storage  # noqa: E402


def main() -> None:
    test_key = f"connectivity-test/{uuid.uuid4().hex}.txt"
    test_content = b"hello from r2 connectivity test"

    print(f"Using storage key: {test_key}")

    # 1. Generate presigned PUT URL
    try:
        upload_url = r2_storage.generate_presigned_upload_url(test_key, "text/plain")
        print("PASS: generated presigned upload URL")
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: could not generate presigned upload URL — {exc}")
        return

    # 2. Upload via that URL (simulates what the frontend will do)
    try:
        resp = requests.put(upload_url, data=test_content, headers={"Content-Type": "text/plain"})
        resp.raise_for_status()
        print("PASS: uploaded test file via presigned URL")
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: upload failed — {exc}")
        return

    # 3. Generate presigned GET URL
    try:
        download_url = r2_storage.generate_presigned_download_url(test_key)
        print("PASS: generated presigned download URL")
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: could not generate presigned download URL — {exc}")
        return

    # 4. Download and verify contents match
    try:
        resp = requests.get(download_url)
        resp.raise_for_status()
        if resp.content == test_content:
            print("PASS: downloaded content matches what was uploaded")
        else:
            print("FAIL: downloaded content does NOT match what was uploaded")
            return
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: download failed — {exc}")
        return

    # 5. Clean up
    try:
        asyncio.run(r2_storage.delete_object(test_key))
        print("PASS: deleted test object")
    except Exception as exc:  # noqa: BLE001
        print(f"WARN: could not delete test object (not fatal) — {exc}")

    print("\nAll checks passed — R2 credentials and bucket are working correctly.")


if __name__ == "__main__":
    main()
