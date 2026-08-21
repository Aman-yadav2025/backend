import asyncio
import argparse
import sys
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine, get_db, SessionLocal
from app.models import Profile, SystemRole

async def provision_admin(clerk_user_id: str, email: str):
    async with SessionLocal() as db:
        # Check if profile exists
        result = await db.execute(select(Profile).where(Profile.id == clerk_user_id))
        profile = result.scalar_one_or_none()

        if profile:
            if profile.system_role == SystemRole.PLATFORM_ADMIN:
                print(f"Profile {clerk_user_id} is already a PLATFORM_ADMIN.")
            else:
                profile.system_role = SystemRole.PLATFORM_ADMIN
                await db.commit()
                print(f"Updated profile {clerk_user_id} to PLATFORM_ADMIN.")
        else:
            profile = Profile(
                id=clerk_user_id,
                email=email,
                system_role=SystemRole.PLATFORM_ADMIN
            )
            db.add(profile)
            await db.commit()
            print(f"Created new profile {clerk_user_id} as PLATFORM_ADMIN.")


def main():
    parser = argparse.ArgumentParser(description="Provision an admin profile in the database for testing")
    parser.add_argument("user_id", help="Clerk user id, e.g. user_2abc...")
    parser.add_argument("--email", default="admin@example.com", help="Email for the profile (default: admin@example.com)")
    args = parser.parse_args()

    asyncio.run(provision_admin(args.user_id, args.email))


if __name__ == "__main__":
    main()
