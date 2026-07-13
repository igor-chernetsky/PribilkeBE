#!/usr/bin/env python3
"""Regenerate the current week's digest (force=True). Run inside the API container."""

from pribilka.db.session import SessionLocal
from pribilka.models.enums import CountryCode
from pribilka.services.weekly_digest import generate_weekly_digest


def main() -> None:
    db = SessionLocal()
    try:
        digest = generate_weekly_digest(db, country=CountryCode.PL, force=True)
        if digest is None:
            print("Digest generation returned None")
            return
        print(digest.id, digest.source, digest.week_start, digest.week_end)
    finally:
        db.close()


if __name__ == "__main__":
    main()
