"""Seed the default admin user.

Safe to run on every boot: skips when ADMIN_EMAIL/ADMIN_PASSWORD are unset
or the admin already exists. Always exits 0 so it never blocks startup.
"""
import os
import sys


def main() -> int:
    email = os.environ.get("ADMIN_EMAIL", "").strip()
    password = os.environ.get("ADMIN_PASSWORD", "").strip()
    if not email or not password:
        print("add_admin: ADMIN_EMAIL/ADMIN_PASSWORD not set - skipping")
        return 0

    from sqlalchemy import select

    from app.core.security import hash_password
    from app.db.session import SessionLocal
    from app.users.models import User

    try:
        db = SessionLocal()
        try:
            if db.scalar(select(User).where(User.email == email)):
                print(f"add_admin: {email} already exists - skipping")
                return 0
            db.add(
                User(
                    email=email,
                    hashed_password=hash_password(password),
                    full_name="Administrator",
                    role="admin",
                )
            )
            db.commit()
            print(f"add_admin: created admin {email}")
            return 0
        finally:
            db.close()
    except Exception as exc:  # never block boot on a seed failure
        print(f"add_admin: failed ({exc}) - continuing boot")
        return 0


if __name__ == "__main__":
    sys.exit(main())
